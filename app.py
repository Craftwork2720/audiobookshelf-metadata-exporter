from flask import Flask, render_template_string, request, flash, redirect, url_for
import abs_export
import os
import re
# NOWY IMPORT: Dodajemy difflib do porównywania podobieństwa tekstów
import difflib

app = Flask(__name__)
app.secret_key = 'super_secret_key_dla_flash_messages' # Required for flash messages

def parse_folder_name(folder_name):
    """
    Parsuje nazwę folderu w formacie: 'Autor - Tytuł' z dopiskami typu 'czyta', 'tom', '[audiobook]'
    """
    import re

    # Usuń część po 'czyta ...'
    cleaned = re.sub(r'czyta .*?(?=\[|$)', '', folder_name, flags=re.IGNORECASE)

    # Usuń nawiasy kwadratowe i ich zawartość, np. [audiobook PL]
    cleaned = re.sub(r'\[.*?\]', '', cleaned)

    # Usuń dopiski typu 'cykl ...' i 'tom X'
    cleaned = re.sub(r'(?i)cykl .*?(?= -|$)', '', cleaned)
    cleaned = re.sub(r'(?i)tom \d+', '', cleaned)

    cleaned = cleaned.strip()

    # Dopasuj: Autor - Tytuł (opcjonalnie z rokiem)
    pattern = r'^(.+?)\s*-\s*(.+?)(?:\s*\((\d{4})\))?$'
    match = re.match(pattern, cleaned)

    if match:
        authors_str, title, year = match.groups()
        authors = [a.strip() for a in authors_str.split(',')]
        return authors, title.strip(), year

    return None, None, None

def normalize_text(text):
    """Normalizuje tekst do porównania - usuwa diakrytyki, zmienia na małe litery"""
    if not text:
        return ""
    
    # Podstawowe mapowanie polskich znaków
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'a', 'Ć': 'c', 'Ę': 'e', 'Ł': 'l', 'Ń': 'n', 'Ó': 'o', 'Ś': 's', 'Ź': 'z', 'Ż': 'z'
    }
    
    normalized = text.lower()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return normalized

# ZMODYFIKOWANA FUNKCJA PORÓWNANIA
def compare_metadata_with_folder(title, author, folder_path):
    """
    Porównuje metadane z nazwą folderu z większą elastycznością.
    Zwraca dict z wynikami porównania.
    """
    import difflib
    if not folder_path:
        return {
            'folder_parsed': False, 'match_status': 'no_path', 'folder_name': '',
            'parsed_title': '', 'parsed_authors': []
        }

    folder_name = os.path.basename(folder_path)
    parsed_authors, parsed_title, parsed_year = parse_folder_name(folder_name)

    if not parsed_title or not parsed_authors:
        return {
            'folder_parsed': False, 'match_status': 'parse_failed', 'folder_name': folder_name,
            'parsed_title': '', 'parsed_authors': []
        }

    # Porównanie tytułów
    normalized_title = normalize_text(title)
    normalized_parsed_title = normalize_text(parsed_title)
    title_similarity = difflib.SequenceMatcher(None, normalized_title, normalized_parsed_title).ratio()
    title_match = (normalized_parsed_title in normalized_title or 
                   normalized_title in normalized_parsed_title or 
                   title_similarity > 0.7)

    # Porównanie autorów z wykorzystaniem podobieństwa tekstu
    metadata_authors = [normalize_text(a) for a in author.split(',')]
    normalized_parsed_authors = [normalize_text(a) for a in parsed_authors]

    authors_match = False
    for meta_author in metadata_authors:
        for folder_author in normalized_parsed_authors:
            similarity = difflib.SequenceMatcher(None, meta_author, folder_author).ratio()
            if similarity > 0.75:
                authors_match = True
                break
        if authors_match:
            break

    # Określenie wyniku
    if title_match and authors_match:
        match_status = 'full_match'
    elif title_match:
        match_status = 'title_only'
    elif authors_match:
        match_status = 'authors_only'
    else:
        match_status = 'no_match'

    return {
        'folder_parsed': True,
        'match_status': match_status,
        'folder_name': folder_name,
        'parsed_title': parsed_title,
        'parsed_authors': parsed_authors
    }


# ZMODYFIKOWANY TEMPLATE - POPRAWIONE KOLORY W TABELI WYNIKÓW
TEMPLATE = """
<!doctype html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Audiobookshelf Exporter</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f4; color: #333; }
        h1, h2 { color: #0056b3; }
        form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        select, button, input[type="text"] { padding: 10px 15px; border-radius: 5px; border: 1px solid #ccc; font-size: 1em; cursor: pointer; }
        button { background-color: #007bff; color: white; border: none; }
        button:hover { background-color: #0056b3; }
        label { margin-right: 10px; margin-bottom: 5px; display: inline-block; }
        input[type="checkbox"] { margin-right: 5px; }
        .item-list { max-height: 400px; overflow-y: auto; border: 1px solid #eee; padding: 10px; background-color: #fdfdfd; border-radius: 5px; margin-top: 15px; }
        .item-list label { display: block; margin-bottom: 5px; padding: 3px 0; }
        .flash { padding: 10px; margin-bottom: 15px; border-radius: 5px; }
        .flash.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .flash.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        ul { list-style-type: none; padding: 0; }
        li { background-color: #fff; padding: 8px 15px; margin-bottom: 5px; border-radius: 5px; border: 1px solid #eee; }
        li strong { color: #007bff; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; }
        .form-group input[type="text"] { width: calc(100% - 22px); }
        #search-input { margin-bottom: 10px; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        
        /* Kolory dopasowania w liście GŁÓWNEJ */
        .match-full { border-left-color: #28a745; }
        .match-title { border-left-color: #ffc107; }
        .match-authors { border-left-color: #17a2b8; }
        .match-none { border-left-color: #dc3545; }
        .match-error { border-left-color: #6c757d; }
        
        /* --- POPRAWIONE STYLE DLA TABELI WYNIKÓW --- */
        /* Zamiast samego koloru tekstu, ustawiamy tło komórki */
        .status-success { background-color: #d4edda; color: #155724; }
        .status-copied { background-color: #d4edda; color: #155724; }
        .status-error { background-color: #f8d7da; color: #721c24; font-weight: bold; }
        .status-missing { background-color: #fff3cd; color: #856404; }
        .status-exists { background-color: #d1ecf1; color: #0c5460; }
        .status-skipped { background-color: #e2e3e5; color: #383d41; }
        .status-info { background-color: #cce5ff; color: #004085; }

        .summary-box {
            background-color: #e9f7ef;
            border: 1px solid #d0e9d9;
            padding: 15px;
            margin-top: 20px;
            border-radius: 8px;
            color: #155724;
        }
        .summary-box p {
            margin: 0 0 5px 0;
            font-weight: bold;
        }
        
        .item-entry {
            border-left: 4px solid #ccc;
            padding-left: 10px;
            margin-bottom: 10px;
        }
        .match-info {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }
        .filter-options {
            margin-bottom: 15px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }
        .filter-options label {
            margin-right: 15px;
            font-weight: normal;
        }
        .legend {
            margin-top: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 5px;
            font-size: 0.9em;
        }
        .legend-item { display: inline-block; margin-right: 20px; margin-bottom: 5px; }
        .legend-color {
            display: inline-block; width: 20px; height: 15px;
            border-radius: 3px; margin-right: 5px; vertical-align: middle;
        }
    </style>
</head>
<body>
<h1>Eksportuj metadane i okładki z katalogów ID Audiobookshelf do wybranego katalogu</h1>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul class="flash-messages">
      {% for category, message in messages %}
        <li class="flash {{ category }}">{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endwith %}

<form method="post" action="/">
  <div class="form-group">
    <label for="library">Wybierz bibliotekę:</label>
    <select name="library" id="library" onchange="this.form.submit()">
      <option value="">-- wybierz --</option>
      {% for lib in libraries %}
        <option value="{{ lib }}" {% if selected_lib == lib %}selected{% endif %}>{{ lib }}</option>
      {% endfor %}
    </select>
  </div>

  <div class="form-group">
    <input type="checkbox" name="compare_folders" id="compare_folders" value="1" 
           {% if compare_folders %}checked{% endif %} onchange="this.form.submit()">
    <label for="compare_folders">Porównaj metadane z nazwami folderów</label>
  </div>

  <input type="hidden" name="library" value="{{ selected_lib }}">
</form>

{% if selected_lib and not items %}
    <p>Brak pozycji do wyeksportowania w wybranej bibliotece lub wystąpił błąd podczas ich pobierania.</p>
{% elif items %}
<form method="post" action="/export">
  <div class="form-group">
    <label for="export_path">Katalog docelowy eksportu:</label>
    <input type="text" id="export_path" name="export_path" value="{{ default_export_path }}" placeholder="np. /exported_audiobooks">
    <small>Pliki zostaną skopiowane do <code>[Katalog docelowy]/[path_z_CSV]</code>.</small><br>
    <small>Okładki i metadane będą szukane w <code>{{abs_media_root}}/[ID_z_CSV]/</code>.</small>
  </div>
  
  <h2>Wybierz pozycje do eksportu ({{ items|length }} znaleziono):</h2>
  
  <div class="form-group">
    <label for="search-input">Szukaj pozycji:</label>
    <input type="text" id="search-input" placeholder="Wpisz tytuł lub autora..." onkeyup="filterItems()">
  </div>
  
  {% if compare_folders %}
  <div class="filter-options">
    <label><input type="checkbox" id="filter-full" checked onchange="filterByMatch()"> Pełne dopasowanie</label>
    <label><input type="checkbox" id="filter-title" checked onchange="filterByMatch()"> Tylko tytuł</label>
    <label><input type="checkbox" id="filter-authors" checked onchange="filterByMatch()"> Tylko autorzy</label>
    <label><input type="checkbox" id="filter-none" checked onchange="filterByMatch()"> Brak dopasowania</label>
    <label><input type="checkbox" id="filter-error" checked onchange="filterByMatch()"> Błąd parsowania</label>
  </div>
  {% endif %}

  <div class="form-group">
    <button type="button" onclick="selectAllItems()">Zaznacz wszystkie widoczne</button>
    <button type="button" onclick="deselectAllItems()">Odznacz wszystkie widoczne</button>
  </div>

  <div class="item-list" id="item-list">
  {% for item_id, path, title, author, comparison in items %}
    <div class="item-entry match-{{ comparison.match_status if comparison else 'none' }}" 
         data-title="{{ title|lower }}" 
         data-author="{{ author|lower }}"
         data-match="{{ comparison.match_status if comparison else 'none' }}">
      <input type="checkbox" name="items" value="{{ item_id }}" id="item-{{ item_id }}">
      <label for="item-{{ item_id }}">
        <strong>{{ title }}</strong> – {{ author }} (ID: {{ item_id }})
        <br><small>Ścieżka: {{ path }}</small>
        {% if comparison and comparison.folder_parsed %}
          <div class="match-info">
            <strong>Folder:</strong> {{ comparison.folder_name }}<br>
            <strong>Sparsowane:</strong> {{ comparison.parsed_authors|join(', ') }} – {{ comparison.parsed_title }}<br>
            <strong>Dopasowanie:</strong> 
            {% if comparison.match_status == 'full_match' %}✓ Pełne dopasowanie
            {% elif comparison.match_status == 'title_only' %}⚠ Tylko tytuł
            {% elif comparison.match_status == 'authors_only' %}⚠ Tylko autorzy
            {% else %}✗ Brak dopasowania
            {% endif %}
          </div>
        {% elif comparison and not comparison.folder_parsed %}
          <div class="match-info">
            <strong>Folder:</strong> {{ comparison.folder_name }}<br>
            <strong>Status:</strong> Nie można sparsować nazwy folderu
          </div>
        {% endif %}
      </label>
    </div>
  {% endfor %}
  </div>
  <input type="hidden" name="library" value="{{ selected_lib }}">
  <button type="submit" style="margin-top: 15px;">Eksportuj zaznaczone</button>
</form>
{% endif %}

{% if results %}
  <h2>Wyniki eksportu:</h2>
  <table>
      <thead>
          <tr>
              <th>ID Pozycji</th>
              <th>metadata.json</th>
              <th>cover.jpg</th>
              <th>Status Ogólny</th>
          </tr>
      </thead>
      <tbody>
          {% for item_id, success, item_details in results %}
          <tr>
              <td><strong>{{ item_id if item_id else 'Ogólny komunikat' }}</strong></td>
              <td class="status-{{ item_details.metadata_class }}">
                  {{ item_details.metadata_status_text }}
              </td>
              <td class="status-{{ item_details.cover_class }}">
                  {{ item_details.cover_status_text }}
              </td>
              <td class="status-{{ item_details.overall_class }}">
                  {{ item_details.overall_message }}
              </td>
          </tr>
          {% endfor %}
      </tbody>
  </table>

  {% if counts %}
    <div class="summary-box">
      <p>Podsumowanie eksportu:</p>
      <p>Liczba skopiowanych plików metadata.json: {{ counts.metadata_total }}</p>
      <p>Liczba skopiowanych plików cover.jpg: {{ counts.cover_total }}</p>
    </div>
  {% endif %}
{% endif %}

<script>
function selectAllItems() {
    var items = document.querySelectorAll('#item-list input[type="checkbox"]');
    items.forEach(function(checkbox) {
        if (checkbox.closest('.item-entry').style.display !== 'none') {
            checkbox.checked = true;
        }
    });
}

function deselectAllItems() {
    var items = document.querySelectorAll('#item-list input[type="checkbox"]');
    items.forEach(function(checkbox) {
        if (checkbox.closest('.item-entry').style.display !== 'none') {
            checkbox.checked = false;
        }
    });
}

function filterItems() {
    var input = document.getElementById('search-input');
    var filter = input.value.toLowerCase();
    var itemEntries = document.querySelectorAll('.item-entry');

    itemEntries.forEach(function(entry) {
        var title = entry.getAttribute('data-title');
        var author = entry.getAttribute('data-author');
        var matchFilter = checkMatchFilter(entry);
        
        var textMatch = title.includes(filter) || author.includes(filter);
        
        if (textMatch && matchFilter) {
            entry.style.display = '';
        } else {
            entry.style.display = 'none';
        }
    });
}

function checkMatchFilter(entry) {
    var matchType = entry.getAttribute('data-match');
    
    var filterFull = document.getElementById('filter-full');
    var filterTitle = document.getElementById('filter-title');
    var filterAuthors = document.getElementById('filter-authors');
    var filterNone = document.getElementById('filter-none');
    var filterError = document.getElementById('filter-error');
    
    if (!filterFull) return true; // Jeśli nie ma filtrów dopasowania, pokaż wszystko
    
    switch(matchType) {
        case 'full_match': return filterFull.checked;
        case 'title_only': return filterTitle.checked;
        case 'authors_only': return filterAuthors.checked;
        case 'no_match': return filterNone.checked;
        case 'parse_failed':
        case 'no_path': return filterError.checked;
        default: return true;
    }
}

function filterByMatch() {
    filterItems();
}

document.addEventListener('DOMContentLoaded', function() {
    var searchInput = document.getElementById('search-input');
    if (searchInput && searchInput.value) {
        filterItems();
    }
    // Upewnij się, że filtrowanie po dopasowaniu jest uruchamiane przy starcie, jeśli filtry są widoczne
    if(document.getElementById('filter-full')) {
        filterByMatch();
    }
});
</script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    libraries = abs_export.list_library_names()
    if not libraries:
        flash("Nie można załadować nazw bibliotek. Upewnij się, że pliki CSV istnieją i są prawidłowe.", "error")

    selected_lib = request.form.get("library") or request.args.get("library")
    compare_folders = request.form.get("compare_folders") == "1" or request.args.get("compare_folders") == "1"
    
    items = []
    results = None
    
    default_export_path = os.environ.get("ABS_EXPORT_DEFAULT_PATH", "/exported_audiobooks") 
    
    if selected_lib:
        lib_id = abs_export.get_library_id_by_name(selected_lib)
        if lib_id:
            raw_items = abs_export.get_items_by_library(lib_id)
            
            items = []
            for item in raw_items:
                item_id, path, title, author = item
                comparison = None
                if compare_folders:
                    comparison = compare_metadata_with_folder(title, author, path)
                items.append((item_id, path, title, author, comparison))
        else:
            flash(f"Nie znaleziono ID dla biblioteki '{selected_lib}'. Sprawdź nazwę w pliku CSV.", "error")

    return render_template_string(TEMPLATE, 
                                  libraries=libraries, 
                                  selected_lib=selected_lib, 
                                  items=items, 
                                  results=results,
                                  default_export_path=default_export_path,
                                  abs_media_root=abs_export.ABS_MEDIA_ROOT,
                                  counts=None,
                                  compare_folders=compare_folders)

@app.route("/export", methods=["POST"])
def export():
    item_ids = request.form.getlist("items")
    selected_lib = request.form.get("library")
    export_path = request.form.get("export_path")
    compare_folders = request.form.get("compare_folders") == "1"

    if not export_path:
        flash("Musisz podać katalog docelowy eksportu.", "error")
        return redirect(url_for('index', library=selected_lib, compare_folders=compare_folders))

    if not item_ids:
        flash("Nie wybrano żadnych pozycji do eksportu.", "error")
        return redirect(url_for('index', library=selected_lib, compare_folders=compare_folders))

    if not selected_lib:
        flash("Brak wybranej biblioteki do eksportu.", "error")
        return redirect(url_for('index'))

    lib_id = abs_export.get_library_id_by_name(selected_lib)
    if not lib_id:
        flash(f"Nie znaleziono ID dla biblioteki '{selected_lib}'. Eksport niemożliwy.", "error")
        return redirect(url_for('index'))

    raw_items = abs_export.get_items_by_library(lib_id)
    if not raw_items:
        flash("Brak pozycji do wyeksportowania w wybranej bibliotece.", "error")
        return redirect(url_for('index', library=selected_lib, compare_folders=compare_folders))

    item_ids_str = [str(i) for i in item_ids]
    items_dict = {str(item[0]): item for item in raw_items}
    selected_items = [items_dict[item_id] for item_id in item_ids_str if item_id in items_dict]

    if not selected_items:
        flash("Wybrane pozycje nie pasują do pozycji w danych. Eksport niemożliwy.", "error")
        return redirect(url_for('index', library=selected_lib, compare_folders=compare_folders))

    results, counts = abs_export.export_items(selected_items, export_path)
    
    has_errors = any(not success for _, success, _ in results)
    if has_errors:
        flash("Eksport zakończony z błędami. Sprawdź wyniki poniżej.", "error")
    else:
        flash("Eksport zakończony pomyślnie!", "success")
    
    libraries = abs_export.list_library_names()
    
    items = []
    for item in raw_items:
        item_id, path, title, author = item
        comparison = None
        if compare_folders:
            comparison = compare_metadata_with_folder(title, author, path)
        items.append((item_id, path, title, author, comparison))

    return render_template_string(TEMPLATE, 
                                  libraries=libraries, 
                                  selected_lib=selected_lib, 
                                  items=items, 
                                  results=results,
                                  default_export_path=export_path,
                                  abs_media_root=abs_export.ABS_MEDIA_ROOT,
                                  counts=counts,
                                  compare_folders=compare_folders)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)