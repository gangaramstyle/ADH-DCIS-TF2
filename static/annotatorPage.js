/* Active dicom - state variables */
var active_dicom = null;
var debug1;


function initializeCornerstone() {
  cornerstoneTools.init({
    showSVGCursors: true,
  });

  cornerstone.enable(element);

  const apiTool = cornerstoneTools['FreehandRoiTool'];
  cornerstoneTools.addTool(apiTool);
  cornerstoneTools.setToolActive('FreehandRoi', { mouseButtonMask: 1 });
  element.addEventListener(cornerstoneTools.EVENTS.MEASUREMENT_COMPLETED, sendAnnotation);
}

const element = document.querySelector('.cornerstone-element');
initializeCornerstone();
cornerstone.registerImageLoader('myImageLoader', loadImage);

updateTable();

function openModal(filename) {
  active_dicom = filename;
  const imageId = 'myImageLoader://'+filename;
  cornerstone.loadImage(imageId).then(function(image) {
      registerMouseEvents();
      getAnnotation((data) => {
        cornerstone.displayImage(element, image);
        cornerstoneTools.clearToolState(element, 'FreehandRoi');
        for (annotation of data) {
          cornerstoneTools.addToolState(element, 'FreehandRoi', annotation);
        }
        setInterval(function(){cornerstone.updateImage(element);},1);
      });
  });
}

function registerMouseEvents() {
  element.addEventListener('mousedown', function (e) {
    let lastX = e.pageX;
    let lastY = e.pageY;
    const mouseButton = e.which;

    function mouseMoveHandler(e) {
      const deltaX = e.pageX - lastX;
      const deltaY = e.pageY - lastY;
      lastX = e.pageX;
      lastY = e.pageY;

      if (mouseButton === 3) {
        let viewport = cornerstone.getViewport(element);
        viewport.voi.windowWidth += (deltaX / viewport.scale);
        viewport.voi.windowCenter += (deltaY / viewport.scale);
        cornerstone.setViewport(element, viewport);
      } else if (mouseButton === 2) {
        let viewport = cornerstone.getViewport(element);
        viewport.translation.x += (deltaX / viewport.scale);
        viewport.translation.y += (deltaY / viewport.scale);
        cornerstone.setViewport(element, viewport);
      }
    }

    function mouseUpHandler() {
      document.removeEventListener('mouseup', mouseUpHandler);
      document.removeEventListener('mousemove', mouseMoveHandler);
    }

    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
  });

  element.addEventListener("wheel", event => {
    const delta = Math.sign(event.deltaY);
    let viewport = cornerstone.getViewport(element);
    viewport.scale += delta * 0.01;
    cornerstone.setViewport(element, viewport);

    // Prevent page from scrolling
    return false;
  });
}

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

function clearAnnotation() {
  var payload = JSON.stringify({
    'toolstate' : [],
    'dicom' : active_dicom
    });
  fetch("/save-region-annotation", {
    method: "POST",
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: payload  })
    .then(resp => {
      if (resp.ok) {
        cornerstoneTools.getToolState(element, 'FreehandRoi').data = [];
        cornerstone.updateImage(element);
        updateTable();
      }
    });
}

function getAnnotation(cback) {
  var payload = JSON.stringify({
    'dicom' : active_dicom
  });
  fetch("/get-region-annotation", {
    method: "POST",
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: payload  })
    .then(resp => {
      if (resp.ok) {
        resp.json().then(data => {
          cback(data);
        });
      }
  });
}

function sendAnnotation() {
  var payload = JSON.stringify({
    'toolstate' : cornerstoneTools.getToolState(element, 'FreehandRoi').data,
    'dicom' : active_dicom
    });
  console.log(payload['toolstate'])
  fetch("/save-region-annotation", {
    method: "POST",
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: payload  })
    .then(resp => {
      if (resp.ok) {
        // technically shouldn't move anything until this is done;
        updateTable();
      }
    });
}

function runModel() {
  fetch("/run-model", {
    method: "POST",
    headers: {
      "Content-Length": 0
    }
  })
    .then(resp => {
      if (resp.ok) {
        //updateTable();
      }
    });
}


function updateTable() {
  fetch("/annotation-table", {
    method: "GET",
  })
    .then(resp => {
      if (resp.ok)
        resp.json().then(data => {
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

              for(var i = 0; i < headerData.length - 1; i++) {
                var headerElem = document.createElement('th');
                headerElem.innerHTML = headerData[i];
                headerRow.append(headerElem);
              }

              var headerElem = document.createElement('th');
              headerElem.innerHTML = "img";
              headerRow.append(headerElem);
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
              for(var j = 0; j < bodyData[i].length - 1; j++) {
                var cell = document.createElement('td');
                cell.innerHTML = bodyData[i][j];
                row.append(cell);
              }
              var cell = document.createElement('td');
              var img = document.createElement('img');
              img.src = "data:image/png;base64, " + bodyData[i][bodyData[i].length - 1];
              cell.appendChild(img);
              row.append(cell);
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