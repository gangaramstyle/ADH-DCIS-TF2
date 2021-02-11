updateTable();


function downloadDataset() {
  fetch("/download-dataset", {
      method: "POST",
    })
  .then(resp => {
    var link = document.createElement('a');
    link.style.display = 'none';
    link.setAttribute('target', '_blank');
    link.setAttribute('href', '/static/dataset.zip');
    link.setAttribute('download', "dataset.zip");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  })
}

function downloadResults() {
  var table_id = "table";
  // Select rows from table_id
  var rows = document.querySelectorAll('table#' + table_id + ' tr');
  // Construct csv
  var csv = [];
  for (var i = 0; i < rows.length; i++) {
      var row = [], cols = rows[i].querySelectorAll('td, th');
      for (var j = 1; j < cols.length; j++) {
          // Clean innertext to remove multiple spaces and jumpline (break csv)
          var data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ')
          // Escape double-quote with double-double-quote (see https://stackoverflow.com/questions/17808511/properly-escape-a-double-quote-in-csv)
          data = data.replace(/"/g, '""');
          // Push escaped string
          row.push('"' + data + '"');
      }
      csv.push(row.join(';'));
  }
  var csv_string = csv.join('\n');
  // Download it
  var filename = 'export_' + table_id + '_' + new Date().toLocaleDateString() + '.csv';
  var link = document.createElement('a');
  link.style.display = 'none';
  link.setAttribute('target', '_blank');
  link.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv_string));
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function updateTable() {
  fetch("/results-table", {
    method: "GET",
  })
    .then(resp => {
      if (resp.ok)
        resp.json().then(data => {
          console.log(data);
          var headerData = data['header'];
          var bodyData = data['body'];
          console.log(headerData);
          if (data['body'].length != 0) {
            // create table if table doesn't exist
            var table = document.getElementById('table');
            if (table === null) {
              table = document.createElement('table');
              table.setAttribute('id', 'table');
              document.getElementById('table-container').append(table);
            }

            // create header if header doesn't exist
            var header = document.getElementById('table-header');
            if (header === null) {
              header = document.createElement('thead');
              header.setAttribute('id', 'table-header');
              table.append(header);

              var headerRow = document.createElement('tr');
              header.append(headerRow);

              for(var i = 0; i < headerData.length; i++) {
                var headerElem = document.createElement('th');
                headerElem.innerHTML = headerData[i];
                headerRow.append(headerElem);
              }
            }


            var body = document.getElementById('table-body');
            if (body === null) {
              body = document.createElement('tbody');
              body.setAttribute('id', 'table-body');
              table.append(body);
            }
            body.innerHTML = "";
            //look, chill, I know  I shouldn't be using the name attribute
            //but it made my life easier
            for(var i = 0; i < bodyData.length; i++) {
              //var rowId = bodyData[i]['rowID'];
              //var updateId = bodyData[i]['updateID'];

              var row = document.createElement('tr');
              row.id = bodyData[i][0];
              row.onclick = function() { openModal(this.id); };

              //row.setAttribute('id', rowId);
              //row.setAttribute('name', updateId);
              var cell = document.createElement('td');
              var img = document.createElement('img');
              img.src = "data:image/png;base64, " + bodyData[i][0];
              cell.appendChild(img);
              row.append(cell);

              for(var j = 1; j < bodyData[i].length; j++) {
                var cell = document.createElement('td');
                cell.innerHTML = bodyData[i][j];
                row.append(cell);
              }

              body.append(row);
            }
          } else {
            console.log("remove table");
            var table = document.getElementById('table');
            document.getElementById('content-container').removeChild(table);
          }
        });
    })
    .catch(err => {
      console.log("An error occured", err.message);
      window.alert("Oops! Something went wrong.");
    });
}