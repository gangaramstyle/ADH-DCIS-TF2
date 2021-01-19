function loadImage(imageId) {
    const width = 256;
    const height = 256;
    const numPixels = width * height;
    var pixelData = new Uint16Array(numPixels);
    const rnd = Math.round(Math.random() * 255);
    let index = 0;
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            pixelData[index] = (x + rnd) % 256;
            index++;
        }
    }

    function getPixelData() {
        return pixelData;
    }

    const image = {
        imageId: imageId,
        minPixelValue: 0,
        maxPixelValue: 255,
        slope: 1.0,
        intercept: 0,
        windowCenter: 127,
        windowWidth: 256,
        render: cornerstone.renderGrayscaleImage,
        getPixelData: getPixelData,
        rows: height,
        columns: width,
        height: height,
        width: width,
        color: false,
        columnPixelSpacing: 1.0,
        rowPixelSpacing: 1.0,
        invert: false,
        sizeInBytes: width * height * 2
    };

    var serverImageData = function(resolve, reject) {
        console.log(imageId);
        return fetch("/get-dicom", {
            method: "POST",
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(imageId.split('//')[1])
        })
          .then(resp => {
            if (resp.ok) {
                resp.json().then(data => {
                    image.minPixelValue = data.minPixelValue;
                    image.maxPixelValue = data.maxPixelValue;
                    image.columns = data.columns;
                    image.width = data.columns;
                    image.rows = data.rows;
                    image.height = data.rows;
                    image.slope = data.slope;
                    image.intercept = data.intercept;
                    image.windowWidth = data.windowWidth
                    image.windowCenter = data.windowCenter
                    image.sizeInBytes = image.width * image.height * 2
                    pixelData = new Uint16Array(data.pixel_data);
                    resolve(image);
                });
            } else {
                reject(new Error('Loading image data from server failed'))
            }
        });
    }

    return {
      promise: new Promise(serverImageData),
      cancelFn: undefined
    }
}


// function loadImage(imageId) {
//     console.log("coolio hotman");
//     fetch("/get-dicom", {
//         method: "POST",
//         headers: {
//             'Accept': 'application/json',
//             'Content-Type': 'application/json'
//         },
//         body: JSON.stringify("ser1538img00001.png")
//     })
//     .then(resp => {
//         if (resp.ok) {
//             resp.json().then(data => {
//                 //data; Uint16Array([1,2,3]);
//                 const width = 256;
//                 const height = 256;
//                 const numPixels = width * height;
//                 const pixelData = new Uint16Array(numPixels);
//                 const rnd = Math.round(Math.random() * 255);
//                 let index = 0;
//                 for (let y = 0; y < height; y++) {
//                     for (let x = 0; x < width; x++) {
//                         pixelData[index] = (x + rnd) % 256;
//                         index++;
//                     }
//                 }

//                 function getPixelData() {
//                     return pixelData;
//                 }

//                 const image = {
//                     imageId: imageId,
//                     minPixelValue: 0,
//                     maxPixelValue: 255,
//                     slope: 1.0,
//                     intercept: 0,
//                     windowCenter: 127,
//                     windowWidth: 256,
//                     render: cornerstone.renderGrayscaleImage,
//                     getPixelData: getPixelData,
//                     rows: height,
//                     columns: width,
//                     height: height,
//                     width: width,
//                     color: false,
//                     columnPixelSpacing: 1.0,
//                     rowPixelSpacing: 1.0,
//                     invert: false,
//                     sizeInBytes: width * height * 2
//                 };

//                 return {
//                     promise: new Promise((resolve) => resolve(image)),
//                     cancelFn: undefined
//                 }
//             });
//         }
//     });
// }