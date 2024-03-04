let sourceImage, markedImage, targetRoot, maState;
let group_pathes = JSON.parse('{{json_group_scans_pathes|safe }}');

function createPagination(pages, page) {
let str = ''//'<ul class="list-group list-group-horizontal">';

    setSourceScan(group_pathes[page-1]["path"], "");

    // Show the Previous button only if you are on a page other than the first
    if (page > 1) {
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+', '+(page-1)+')">Previous</a>';
    }

    // Show the very first page followed by a "..." at the beginning of the
    // pagination section (after the Previous button)
    if (page > 1) {
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+', 1)">1</a>';
        if (page > 2) {
            str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+','+(page-2)+')">...</a>';
        }
    }
    // Determine how many pages to show after the current page index
    if (page === 1) {
        <!-- pageCutHigh += 1; -->
    } else if (page === 2) {
        <!-- pageCutHigh += 0; -->
    }
    // Determine how many pages to show before the current page index
    if (page === pages) {
        <!-- pageCutLow -= 1; -->
    } else if (page === pages-1) {
        <!-- pageCutLow -= 0; -->
    }
    // active page
    str += '<a class="list-group-item list-group-item-action active" onclick="createPagination('+pages+', '+page+')">'+page +'</a>';

    // Show the very last page preceded by a "..." at the end of the pagination
    // section (before the Next button)
    if (page < pages-1) {
        if (page < pages-2) {
            str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+','+(page+2)+')">...</a>';
        }
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+','+pages+')">'+pages+'</a>';
    }
    // Show the Next button only if you are on a page other than the last
    if (page < pages) {
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination('+pages+','+(page+1)+')">Next</a>';
    }

    // Return the pagination string to be outputted in the pug templates
    document.getElementById("pagination").innerHTML = str;
    setMarkerArea();
    return str;
}

function setSourceScan(scan_path){
    old_source = document.getElementById("source_img").src;
    sourceImage = document.getElementById("source_img");
    sourceImage.src = scan_path;
    targetRoot = sourceImage.parentElement;
    old_marked = document.getElementById("marked_img").src;
    markedImage = document.getElementById("marked_img");
    markedImage.src = scan_path;

    // change current and last source element background color
    currSourceIdSplit = scan_path.split('/').pop().split('.').slice(-2)[0].split('_');
    currSourceElementId =
    currSourceIdSplit[0]+"_"+parseFloat(currSourceIdSplit[1])+"_"+parseFloat(currSourceIdSplit[2].replace("x","."));
    if (old_source){
        lastSourceIdSplit = old_source.split('/').pop().split('.').slice(-2)[0].split('_');
        lastSourceElementId =
        lastSourceIdSplit[0]+"_"+parseFloat(lastSourceIdSplit[1])+"_"+parseFloat(lastSourceIdSplit[2].replace("x","."));
        document.getElementById(lastSourceElementId).style.backgroundColor = "";
    }
    document.getElementById(currSourceElementId).style.backgroundColor = "yellow";
}

function setMarkerArea(){

    //sourceImage = document.getElementById("source_img");
    //markedImage = document.getElementById("marked_img" );
    //targetRoot = sourceImage.parentElement;

    //MarkerArea settings
    const markerArea = new markerjs2.MarkerArea(sourceImage);
    markerArea.uiStyleSettings.redoButtonVisible = true;
    markerArea.uiStyleSettings.notesButtonVisible = true;
    markerArea.uiStyleSettings.zoomButtonVisible = true;
    markerArea.uiStyleSettings.zoomOutButtonVisible = true;
    markerArea.uiStyleSettings.clearButtonVisible = true;
    markerArea.uiStyleSettings.resultButtonBlockVisible = false

    // set position to parent div to align
    markerArea.targetRoot = targetRoot;

    markerArea.addEventListener("render", (event) => {
        markedImage.src = event.dataUrl;
        // save the state of MarkerArea
        // maState = event.state;
    });


    // register an event listener for when user clicks OK/save in the marker.js UI
    markerArea.addRenderEventListener(dataUrl => {
    // we are setting the markup result to replace our original image on the page
    // but you can set a different image or upload it to your server
        markedImage = document.getElementById("marked_img");
        markedImage.src = dataUrl;
    });


    // Event Listeners for create/delete and change
    markerArea.addEventListener("markercreate", (event) => {
        imgsrc_split = sourceImage.src.split('/').pop().split('.').slice(-2)[0].split('_');
        copy_no = currSourceIdSplit[1];
        page_no = currSourceIdSplit[2];

        markerArea.startRenderAndClose();

        saveMarkers("{{ exam.pk }}","{{ pages_group.pk }}",copy_no,page_no,JSON.stringify(markerArea.getState()),markedImage.src,"None",sourceImage.getAttribute("src"));

        //maState = markerArea.getState();
        //markerArea.show();
        //markerArea.restoreState(maState);
        setMarkerArea();

        $( "#pages_group_list" ).load(window.location.href + " #pages_group_list" );
        initCopyPagesTableOnClickRowEvent(true);
        document.getElementById(currSourceElementId).style.backgroundColor = "yellow";
    });

    markerArea.addEventListener("markerdelete", (event) => {
        alert('delete');
    });

    markerArea.addEventListener("markerchange", (event) => {
        alert('change');
    });

    //get Markers (state) if exist
    imgsrc_split = sourceImage.src.split('/').pop().split('.').slice(-2)[0].split('_');
    copy_no = currSourceIdSplit[1];
    page_no = currSourceIdSplit[2];

    maState = getMarkers("{{ exam.pk }}",copy_no,page_no,sourceImage.getAttribute("src"));
    markerArea.show();
    if(maState && maState!="None"){
        markerArea.restoreState(maState);
    }
}

function initCopyPagesTableOnClickRowEvent(refresh){

    $("#table-copies-pages").on('click', 'tr', function () {
        createPagination({{ scans_pathes_list|length }}, parseFloat(this.cells[0].innerText));
    });

    if(!refresh){
        var table = $("#table-copies-pages").DataTable( {
            scrollY: '85vh',
            "dom": 'rtip',
            "lengthChange": false,
            "paging": false
        } );
    }
}

function saveMarkers(pk,group_pk,copy_no,page_no,markers,marked_img_dataUrl,comment,filename){
    $.ajax({
        url : "{% url 'save_markers' %}",
        async : false,
        type : "POST",
        data : {
            'csrfmiddlewaretoken' : "{{ csrf_token }}",
            'exam_pk' : pk,
            'reviewGroup_pk' : group_pk,
            'copy_no' : copy_no,
            'page_no' : ""+page_no,
            'markers' : markers,
            'marked_img_dataUrl' : marked_img_dataUrl,
            'comment' : comment,
            'filename' : filename
        },
        beforeSend : function(){
            $('#loadingModal').modal('show');
        },
        complete: function () {
            $('#loadingModal').modal('hide');
        }
    });
}

function getMarkers(pk,copy_no,page_no,filename){
    var markers;
    $.ajax({
        url: "{% url 'get_markers' %}",
        async : false,
        type: "POST",
        data : {
            'csrfmiddlewaretoken' : "{{ csrf_token }}",
            'exam_pk' : pk,
            'copy_no' : copy_no,
            'page_no' : ""+page_no,
            'filename' : filename
        },
        success: (data) => {
            markers="None";
            if(data!="None"){
                markers=JSON.parse(data);
            }
        },
        error: (error) => {
            console.log(error);
        }
    });
    return markers;
}

$(function() {
    var saveComment = function(data) {

    // Convert pings to human readable format
    $(Object.keys(data.pings)).each(function(index, userId) {
        var fullname = data.pings[userId];
        var pingText = '@' + fullname;
        data.content = data.content.replace(new RegExp('@' + userId, 'g'), pingText);
    });

    return data;
}

$('#comments-container').comments({
    profilePictureURL: 'https://viima-app.s3.amazonaws.com/media/public/defaults/user-icon.png',
    currentUserId: 1,
    roundProfilePictures: true,
    textareaRows: 1,
    enableAttachments: true,
    enableHashtags: true,
    enablePinging: true,
    scrollContainer: $(window),
    searchUsers: function(term, success, error) {
        setTimeout(function() {
            success(usersArray.filter(function(user) {
                var containsSearchTerm = user.fullname.toLowerCase().indexOf(term.toLowerCase()) != -1;
                var isNotSelf = user.id != 1;
                return containsSearchTerm && isNotSelf;
            }));
        }, 500);
    },
    getComments: function(success, error) {
        setTimeout(function() {
            success(commentsArray);
        }, 500);
    },
    postComment: function(data, success, error) {
        setTimeout(function() {
            success(saveComment(data));
        }, 500);
    },
    putComment: function(data, success, error) {
        setTimeout(function() {
            success(saveComment(data));
        }, 500);
    },
    deleteComment: function(data, success, error) {
        setTimeout(function() {
            success();
        }, 500);
    },
    upvoteComment: function(data, success, error) {
        setTimeout(function() {
            success(data);
        }, 500);
    },
    validateAttachments: function(attachments, callback) {
        setTimeout(function() {
            callback(attachments);
        }, 500);
    },
});


$(window).on("load",function(){
    initCopyPagesTableOnClickRowEvent(false);
    {% if currpage > 0 %}
    createPagination({{ scans_pathes_list|length }}, {{ currpage }})
    {% else %}
    createPagination({{ scans_pathes_list|length }}, 1);
    {% endif %}

    //hide top and side bars
    var wrapper = document.getElementById("wrapper")
    var topb = document.getElementById("topbar-wrapper");
    var sideb = document.getElementById("sidebar-wrapper");
    wrapper.style.paddingLeft = "20px";
    topb.style.display = "none";
    sideb.style.display = "none";

});