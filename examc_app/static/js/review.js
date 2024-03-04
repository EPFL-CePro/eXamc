let sourceImage, target, targetRoot, maState, markerArea,groups_paths;

function createPagination(group_name, pages, page) {
    let str = ''//'<ul class="list-group list-group-horizontal">';

    // Set source image for markerjs
    setSourceScan(groups_paths[""+group_name+""][page-1]["path"], group_name);

    // Show the Previous button only if you are on a page other than the first
    if (page > 1) {
      str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+', '+(page-1)+')">Previous</a>';
    }

    // Show the very first page followed by a "..." at the beginning of the
    // pagination section (after the Previous button)
    if (page > 1) {
      str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+', 1)">1</a>';
      if (page > 2) {
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+','+(page-2)+')">...</a>';
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
    str += '<a class="list-group-item list-group-item-action active"onclick="createPagination(\''+group_name+'\', '+pages+', '+page+')">'+ page +'</a>';

    // Show the very last page preceded by a "..." at the end of the pagination
    // section (before the Next button)
    if (page < pages-1) {
      if (page < pages-2) {
        str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+','+(page+2)+')">...</a>';
      }
      str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+','+pages+')">'+pages+'</a>';
    }
    // Show the Next button only if you are on a page other than the last
    if (page < pages) {
      str += '<a class="list-group-item list-group-item-action" onclick="createPagination(\''+group_name+'\', '+pages+','+(page+1)+')">Next</a>';
    }

    // Return the pagination string to be outputted in the pug templates
    document.getElementById("pagination-"+group_name).innerHTML = str;
    target = document.getElementById("marked_img-"+group_name);
    setMarkerArea(group_name);
    return str;
  }

function showMarkerArea(target) {
  const markerArea = new markerjs2.MarkerArea(sourceImage);
  // since the container div is set to position: relative it is now our positioning root
  // end we have to let marker.js know that
  markerArea.targetRoot = targetRoot;
  markerArea.addRenderEventListener((imgURL, state) => {
    target.src = imgURL;
    // save the state of MarkerArea
    maState = state;
    });
    markerArea.show();
    // if previous state is present - restore it
    if (maState) {
      markerArea.restoreState(maState);
    }
  }

function setSourceScan(scan_path, group_name){
  old_source = document.getElementById("source_img-"+group_name).src;
  document.getElementById("source_img-"+group_name).src = scan_path;
  document.getElementById("marked_img-"+group_name).src = scan_path;

  // change current and last source element background color
  currSourceIdSplit = scan_path.split('/').pop().split('.').slice(-2)[0].split('_');
  currSourceElementId = currSourceIdSplit[0]+"_"+parseInt(currSourceIdSplit[1])+"_"+parseInt(currSourceIdSplit[2]);
  if (old_source){
    lastSourceIdSplit = old_source.split('/').pop().split('.').slice(-2)[0].split('_');
    lastSourceElementId = lastSourceIdSplit[0]+"_"+parseInt(lastSourceIdSplit[1])+"_"+parseInt(lastSourceIdSplit[2]);
    document.getElementById(lastSourceElementId).style.backgroundColor = "";
  }
  document.getElementById(currSourceElementId).style.backgroundColor = "yellow";
}

function initPagination(){
  groups_paths = JSON.parse('{{json_groups_scans_pathes|safe }}');
  {% for key, value in scans_pathes_list.items %}
  createPagination("{{ key|cut:' ' }}",{{ value|length }}, 1);
  {% endfor %}
}

function setMarkerArea(group_name){
  sourceImage = document.getElementById("source_img-"+group_name);
  target = document.getElementById("marked_img-"+group_name );
  targetRoot = sourceImage.parentElement;

  //MarkerArea settings
  markerArea = new markerjs2.MarkerArea(sourceImage);
  markerArea.uiStyleSettings.redoButtonVisible = true;
  markerArea.uiStyleSettings.notesButtonVisible = true;
  markerArea.uiStyleSettings.zoomButtonVisible = true;
  markerArea.uiStyleSettings.zoomOutButtonVisible = true;
  markerArea.uiStyleSettings.clearButtonVisible = true;
  markerArea.uiStyleSettings.resultButtonBlockVisible = false

  // set position to parent div to align
  markerArea.targetRoot = targetRoot;

  markerArea.addRenderEventListener((imgURL, state) => {
    target.src = imgURL;
    // save the state of MarkerArea
    maState = state;
    markerArea.show();
    // if previous state is present - restore it
    if (maState) {
      markerArea.restoreState(maState);
    }
  });

  //
  markerArea.addEventListener("markercreate", (event) => {
    alert('create');
  });
  markerArea.addEventListener("markerdelete", (event) => {
    alert('delete');
  });
  markerArea.addEventListener("markerchange", (event) => {
    alert('change');
  });

  showMarkerArea(target);
}

<!-- function initMarkerAreas() {

  {% for key, value in scans_pathes_list.items %}
  setMarkerArea("{{ key }}");
  {% endfor %}

} -->

<!-- function initSourcesScans(){
  {% for key, value in scans_pathes_list.items %}
      setSourceScan("{{ value.0.path }}","{{ key|cut:' ' }}");
  {% endfor %}
} -->

function initCopyPagesTableOnClickRowEvent(){
  {% for key, value in scans_pathes_list.items %}

    $("#table-copies-pages-{{ key|cut:' '}}").on('click', 'tr', function () {
      createPagination("{{ key }}",{{ value|length }}, parseInt(this.cells[0].innerText));
    });

    var table = $("#table-copies-pages-{{ key|cut:' '}}").DataTable( {
        scrollY:    '900px',
        "dom": 'rtip',
        "lengthChange": false,
        "paging": false
    } );

  {% endfor %}
}

$(window).on("load",function(){
  initSourceScans();
  initMarkerAreas();
  //showMarkerArea();
  initPagination();
  initCopyPagesTableOnClickRowEvent();

  $('a[data-toggle="pill"]').on('shown.bs.tab', function (e) {
    var target = $(e.target).attr("href") // activated tab
    if(target!="#pills-review-summary"){
      alert(target.split('_').pop())
    }
  });

});
