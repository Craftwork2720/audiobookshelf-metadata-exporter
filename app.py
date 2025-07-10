from flask import Flask, render_template_string, request, flash, redirect, url_for
import abs_export
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key_dla_flash_messages' # Required for flash messages

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

        /* Table specific styles */
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
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        /* Status colors */
        .status-copied { color: green; } /* New: indicates successful copy */
        .status-success { color: green; } /* General success */
        .status-error { color: red; font-weight: bold; }
        .status-missing { color: orange; } /* Missing source file */
        .status-exists { color: blue; } /* File already exists at destination */
        .status-skipped { color: gray; } /* Item skipped due to no source files */
        .status-info { color: #0056b3; } /* General info messages */

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

  <div class="form-group">
    <button type="button" onclick="selectAllItems()">Zaznacz wszystkie widoczne</button>
    <button type="button" onclick="deselectAllItems()">Odznacz wszystkie widoczne</button>
  </div>

  <div class="item-list" id="item-list">
  {% for item_id, path, title, author in items %} {# Zmieniono relPath na path #}
    <div class="item-entry" data-title="{{ title|lower }}" data-author="{{ author|lower }}">
      <input type="checkbox" name="items" value="{{ item_id }}" id="item-{{ item_id }}">
      <label for="item-{{ item_id }}">{{ title }} – {{ author }} (ID: {{ item_id }}, Ścieżka: {{ path }})</label> {# Zmieniono Ścieżka rel. na Ścieżka #}
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
        
        if (title.includes(filter) || author.includes(filter)) {
            entry.style.display = '';
        } else {
            entry.style.display = 'none';
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    var searchInput = document.getElementById('search-input');
    if (searchInput && searchInput.value) {
        filterItems();
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
    items = []
    results = None
    
    default_export_path = os.environ.get("ABS_EXPORT_DEFAULT_PATH", "/exported_audiobooks") 
    
    if selected_lib:
        lib_id = abs_export.get_library_id_by_name(selected_lib)
        if lib_id:
            items = abs_export.get_items_by_library(lib_id)
        else:
            flash(f"Nie znaleziono ID dla biblioteki '{selected_lib}'. Sprawdź nazwę w pliku CSV.", "error")

    return render_template_string(TEMPLATE, 
                                  libraries=libraries, 
                                  selected_lib=selected_lib, 
                                  items=items, 
                                  results=results,
                                  default_export_path=default_export_path,
                                  abs_media_root=abs_export.ABS_MEDIA_ROOT,
                                  counts=None)

@app.route("/export", methods=["POST"])
def export():
    item_ids = request.form.getlist("items")
    selected_lib = request.form.get("library")
    export_path = request.form.get("export_path")

    if not export_path:
        flash("Musisz podać katalog docelowy eksportu.", "error")
        return redirect(url_for('index', library=selected_lib))

    if not item_ids:
        flash("Nie wybrano żadnych pozycji do eksportu.", "error")
        return redirect(url_for('index', library=selected_lib))

    if not selected_lib:
        flash("Brak wybranej biblioteki do eksportu.", "error")
        return redirect(url_for('index'))

    lib_id = abs_export.get_library_id_by_name(selected_lib)
    if not lib_id:
        flash(f"Nie znaleziono ID dla biblioteki '{selected_lib}'. Eksport niemożliwy.", "error")
        return redirect(url_for('index'))

    all_items = abs_export.get_items_by_library(lib_id)
    if not all_items:
        flash("Brak pozycji do wyeksportowania w wybranej bibliotece.", "error")
        return redirect(url_for('index', library=selected_lib))

    item_ids_str = [str(i) for i in item_ids]
    items_dict = {str(item[0]): item for item in all_items}
    selected_items = [items_dict[item_id] for item_id in item_ids_str if item_id in items_dict]

    if not selected_items:
        flash("Wybrane pozycje nie pasują do pozycji w danych. Eksport niemożliwy.", "error")
        return redirect(url_for('index', library=selected_lib))

    results, counts = abs_export.export_items(selected_items, export_path)
    
    has_errors = any(not success for _, success, _ in results)
    if has_errors:
        flash("Eksport zakończony z błędami. Sprawdź wyniki poniżej.", "error")
    else:
        flash("Eksport zakończony pomyślnie!", "success")
    
    libraries = abs_export.list_library_names()
    items = abs_export.get_items_by_library(lib_id)

    return render_template_string(TEMPLATE, 
                                  libraries=libraries, 
                                  selected_lib=selected_lib, 
                                  items=items, 
                                  results=results,
                                  default_export_path=export_path,
                                  abs_media_root=abs_export.ABS_MEDIA_ROOT,
                                  counts=counts)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)