var globalMaskClassPaths = [];
var structureLayers = [];
var mask_path;

var imgsParmsHolders = [];
var imgParmsIVD = [];
var imgParmsPE = [];
var imgParmsTS = [];
var imgParmsAAP = [];

/**
 * Image upload image function
 */
function handleImageUpload() {
    var imageInput = document.getElementById('imageUpload');
    var submitButton = document.getElementById('submitImage');
    if (imageInput.files && imageInput.files[0]) {
        // Enable the submit button
        submitButton.disabled = false;
        // Display the uploaded image
        displayUploadedImage();
    } else {
        // Disable the submit button if no image is chosen
        submitButton.disabled = true;
    }
}

/**
 * Display upload image function
 */
function displayUploadedImage() {
    var input = document.getElementById('imageUpload');
    var editButton = document.getElementById('editImage');
    // var overlayBtn = document.getElementById('processIamge')
    if (input.files && input.files[0]) {
        var reader = new FileReader();

        reader.onload = function(e) {
            $('#imagePlaceholder1').attr('src', e.target.result);
            // $('#imageOrigin').attr('src', e.target.result);
        }

        reader.readAsDataURL(input.files[0]);
        editButton.disabled = false
        // overlayBtn.disabled = false;
    }
    else {
        editButton.disabled = true
        // overlayBtn.disabled = true;
    }
}

function getCSRFToken() {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var cookie = jQuery.trim(cookies[i]);
        if (cookie.substring(0, 'csrftoken'.length + 1) === 'csrftoken=') {
            return decodeURIComponent(cookie.substring('csrftoken'.length + 1));
        }
    }
    return null;
}

/**
 * This function will upload the image to the model and generate the output png files in media folder 
 */
function uploadImage() {
    var formData = new FormData();
    formData.append('image', $('#imageUpload')[0].files[0]);
    var csrftoken = getCSRFToken();

    $.ajax({
        type: 'POST',
        url: '/api/process-image/',
        data: formData,
        processData: false,
        contentType: false,
        beforeSend: function(xhr) {
            if (csrftoken) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        },
        success: function(response) {
            // Extract relevant data from the response
            var maskUrl = response.mask_url;
            // Second API call: view_mask
            $.ajax({
                type: 'POST',
                url: '/api/view-mask/',
                data: { 'mask_url': maskUrl },  // Pass relevant data to the second API
                success: function(viewMaskResponse) {
                    // Handle the response of the second API as needed
                    $('#imagePlaceholder2').attr('src', viewMaskResponse.mask_url)
                    globalMaskClassPaths = viewMaskResponse.mask_class_paths;
                    mask_path = viewMaskResponse.mask_url;
                    initalizeImages()
                    addBKGtoCanvas()
                },
                error: function() {
                    console.error('Error calling view_mask API');
                }
            });
        },
        error: function() {
            console.error('Error processing image');
        }
    });
}


function initalizeImages() {
    
    if (globalMaskClassPaths.length == 0) {
        console.log("Images are not generated! Please check the code!")
        alert("Error! Images are missing!")
        return
    }
    
    $('#imageIVD').attr('src', globalMaskClassPaths[0])
    $('#imagePE').attr('src', globalMaskClassPaths[1])
    $('#imageTS').attr('src', globalMaskClassPaths[2])
    $('#imageAAP').attr('src', globalMaskClassPaths[3])

    // Angle, Left, Top, ScaleX, ScaleY
    imgParmsIVD = [0,0,0,2,2]
    imgParmsPE = [0,0,0,2,2]
    imgParmsTS = [0,0,0,2,2]
    imgParmsAAP = [0,0,0,2,2]
    imgsParmsHolders = [imgParmsIVD,imgParmsPE,imgParmsTS,imgParmsAAP]
}

/**
 * Reset Btn corresponding image's layer.
 * @param {*} btnObj 
 */
function resetBtn(btnObj) {
    if (btnObj.value == "IVD") {$('#imageIVD').attr('src', globalMaskClassPaths[0])}
    if (btnObj.value == "PE") {$('#imagePE').attr('src', globalMaskClassPaths[1])}
    if (btnObj.value == "TS") {$('#imageTS').attr('src', globalMaskClassPaths[2])}
    if (btnObj.value == "AAP") {$('#imageAAP').attr('src', globalMaskClassPaths[3])}
    alert(btnObj.value + " Image reset!")
}

/**
 * This function will make sure there is only one checkbox is selected under the selected elementName.
 * @param {*} checkbox This is a html checkbox element
 */
function onlyOne(checkbox) {
    var checkboxes = document.getElementsByName('typeCheck')
    checkboxes.forEach((item) => {
        if (item !== checkbox) {
            item.checked = false
            document.getElementById("resetBtn" + item.value).disabled = true
            document.getElementById("image" + item.value).hidden = true
            document.getElementById("hideBtn" + item.value).disabled = true
            document.getElementById("resetPos" + item.value).disabled = true
            // centerPos(item)
        }
    })
    if (checkbox.checked) {
        document.getElementById("resetBtn" + checkbox.value).disabled = false
        document.getElementById("image" + checkbox.value).hidden = false
        document.getElementById("hideBtn" + checkbox.value).disabled = false
        document.getElementById("resetPos" + checkbox.value).disabled = false


    } else {
        document.getElementById("resetBtn" + checkbox.value).disabled = true
        document.getElementById("image" + checkbox.value).hidden = true
        document.getElementById("hideBtn" + checkbox.value).disabled = true
        document.getElementById("resetPos" + checkbox.value).disabled = true
        // centerPos(checkbox)
    }
}


function onlyOneV2(checkbox) {
    var checkboxes = document.getElementsByName('typeCheck')
    var resetBtn = document.getElementById('resetBtn')
    var saveBtn = document.getElementById('saveBtn')

    checkboxes.forEach((item) => {
        if (item !== checkbox) {
            item.checked = false
            resetBtn.value = ""
            saveBtn.value = ""
            removeImg(checkbox.value)            
        }
    })
    if (checkbox.checked) {
        resetBtn.value = checkbox.value
        saveBtn.value = checkbox.value
        showImg(checkbox.value)
    } else {
        resetBtn.value = ""
        saveBtn.value = "" 
        removeImg(checkbox.value)
    }
}