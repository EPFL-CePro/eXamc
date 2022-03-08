from django.shortcuts import render
from examreview_app.utils.import_scans import *

# Create your views here.
def home(request):
    return render(request, 'home.html')

def test_function(request):
    split_scans_by_copy('2022','1','PREPA-004')
    return render(request, 'home.html')
