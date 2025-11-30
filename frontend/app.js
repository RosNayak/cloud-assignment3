// Replace with your actual API key
const API_KEY = 'ne2iGSoyzW54hxV0XlTHf8tGsAjxXbp788gOHrdg';

// Create API Gateway client
var apigClient = apigClientFactory.newClient({
  apiKey: API_KEY
});

// Hook up buttons
document.getElementById('searchBtn').addEventListener('click', performSearch);
document.getElementById('uploadBtn').addEventListener('click', uploadPhoto);

// ---------------------------------------------------------
// SEARCH: call GET /search?q=<query>
// ---------------------------------------------------------
function performSearch() {
  const query = document.getElementById('searchQuery').value.trim();
  if (!query) {
    alert('Please enter a search query');
    return;
  }

  const params = { q: query };
  const body = {};  // GET → no body
  const additionalParams = {};

  // Adjust 'searchGet' if your SDK uses a different name
  apigClient.searchGet(params, body, additionalParams)
    .then(function (response) {
      console.log('Search response:', response);
      // Expect response.data.results = array from Lambda
      const results = response.data.results || response.data; // depending on your Lambda
      console.log('Search response:', response);
      renderResults(results);
    })
    .catch(function (error) {
      console.error('Search error:', error);
      alert('Search failed, see console for details');
    });
}

function renderResults(results) {
  const container = document.getElementById('results');
  container.innerHTML = '';

  if (!results || results.length === 0) {
    container.textContent = 'No results.';
    return;
  }

  results.forEach(item => {
    // Expect item.bucket and item.objectKey from ES document
    const bucket = item.bucket;
    const key = item.objectKey;

    // Public S3 URL (if your photo bucket is public)
    const url = `https://${bucket}.s3.amazonaws.com/${encodeURIComponent(key)}`;

    const img = document.createElement('img');
    img.src = url;
    img.alt = key;

    container.appendChild(img);
  });
}

// ---------------------------------------------------------
// UPLOAD: call PUT /photos?object=<file-name>
//         with x-amz-meta-customLabels header
// ---------------------------------------------------------
function uploadPhoto() {
  const fileInput = document.getElementById('photoFile');
  const labelsInput = document.getElementById('customLabels').value.trim();
  const file = fileInput.files[0];

  if (!file) {
    alert('Please choose an image file to upload.');
    return;
  }

  const objectKey = file.name;

  // Query string params (object becomes {object} in S3 path override)
  const params = {
    object: objectKey,
    'x-amz-meta-customLabels': labelsInput  // e.g. "car, wheel"
  };

  // Body is the binary file
  const body = file;

  // Headers (metadata + content type)
  const additionalParams = {
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
    }
  };

  // Adjust 'photosPut' if your SDK uses a different name
  apigClient.photosPut(params, body, additionalParams)
    .then(function (response) {
      console.log('Upload response:', response);
      alert('Upload succeeded!');
      // Optional: clear fields
      fileInput.value = '';
      document.getElementById('customLabels').value = '';
    })
    .catch(function (error) {
      console.error('Upload error:', error);
      alert('Upload failed, see console for details');
    });
}
