/* Upload state - state variables */
var uploads_table = [["Total upload", "0%"]];
var file_row_map = {}

/* Resumable code */

var r = new Resumable({
  target: '/resumable',
  testChunks: true,
  query: function(file) {
    return {tag: document.getElementById('tag').value};
  }
});

r.assignDrop(document.getElementById("file-drag"));
r.assignBrowse(document.getElementById("file-upload"));

r.on('fileAdded', (file) => {
  file_exists(file.file.name, (exists) => {
    if (!exists) {
      file_row_map[file.fileName] = uploads_table.push([file.fileName, "0%"]) - 1;
      writeTable_UploaderPage(uploads_table);
      r.upload();
    } else {
      file.abort();
    }
  });
});

r.on('fileSuccess', (file, message) => {
  //updateTable()
});

r.on('fileProgress', (file, ratio) => {
  uploads_table[file_row_map[file.fileName]][1] =
   parseFloat(file.progress()*100).toFixed(0)+"%";
  writeTable_UploaderPage(uploads_table);
});

r.on('complete', () => {
  console.log("complete");
  document.getElementById("annotate_btn").disabled = false;
  document.getElementById("clear_btn").disabled = false;
});


r.on('progress', () => {
  uploads_table[0][1] =
   parseFloat(r.progress()*100).toFixed(0)+"%";
  writeTable_UploaderPage(uploads_table);
});

function file_exists(filename, callback) {
  fetch("/file-exists", {
    method: "POST",
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(filename) })
    .then(resp => {
      if (resp.ok) {
        resp.json().then(data => {
          callback(data);
        });
      }
  });
}

function delete_all_files() {
  fetch("/delete-all", {
    method: "POST",
    headers: {
      "Content-Length": 0
    } })
    .then(resp => {
      if (resp.ok) {
        uploads_table.splice(1);
        writeTable_UploaderPage(uploads_table);
      }
  });
}

function delete_file(filename) {
  fetch("/delete-file", {
    method: "POST",
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(filename) })
    .then(resp => {
      if (resp.ok) {
        uploads_table.splice(file_row_map[filename], 1);
        writeTable_UploaderPage(uploads_table);
      }
  });
}


function writeTable_UploaderPage(two_d_array) {
  var headerData = two_d_array[0];
  var bodyData = two_d_array.slice(1);
  if (bodyData.length != 0) {
    // create table if table doesn't exist
    var table = document.getElementById('table');
    if (table === null) {
      table = document.createElement('table');
      table.setAttribute('id', 'table');
      document.getElementById('content-container').append(table);
    }

    // create header if header doesn't exist
    var header = document.getElementById('table-header');
    if (header === null) {
      header = document.createElement('thead');
      header.setAttribute('id', 'table-header');
      table.append(header);
    }
    header.innerHTML = "";
    var headerRow = document.createElement('tr');
    header.append(headerRow);

    for(var i = 0; i < headerData.length; i++) {
      var headerElem = document.createElement('th');
      headerElem.innerHTML = headerData[i];
      headerRow.append(headerElem);
    }

    var body = document.getElementById('table-body');
    if (body === null) {
      body = document.createElement('tbody');
      body.setAttribute('id', 'table-body');
      table.append(body);
    }
    body.innerHTML = "";
    //look, chill, I know  I shouldn't be using the 'name' attribute
    //but it made my life easier
    for(var i = 0; i < bodyData.length; i++) {
      //var rowId = bodyData[i]['rowID'];
      //var updateId = bodyData[i]['updateID'];

      var row = document.createElement('tr');
      row.id = bodyData[i][0];
      row.onclick = function() { openModal(this.id); };

      //row.setAttribute('id', rowId);
      //row.setAttribute('name', updateId);
      for(var j = 0; j < bodyData[i].length; j++) {
        var cell = document.createElement('td');
        cell.innerHTML = bodyData[i][j];
        row.append(cell);
      }
      body.append(row);
    }
  } else {
    var table = document.getElementById('table');
    document.getElementById('content-container').removeChild(table);
  }

}