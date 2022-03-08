# SCANS IMPORT functions
from django.conf import settings
import pyzbar.pyzbar as pyzbar
import numpy as np
import cv2
import os
import imghdr

# Detect QRCodes on scans, split copies in subfolders and check nb pages
def split_scans_by_copy(year,semester,exam_code):
    scans_dir = str(settings.SCANS_ROOT)+"/"+year+"/"+semester+"/"+exam_code

    copy_nr = 0;
    current_subdir = scans_dir
    page_nr = 0
    pages_by_copy = []
    for filename in sorted(os.listdir(scans_dir)):
        f = os.path.join(scans_dir, filename)
        # checking if it is a jpeg file
        if imghdr.what(f) == 'jpeg':
            # Read image
            im = cv2.imread(f)
            decodedObjects = pyzbar.decode(im)

            for obj in decodedObjects:
                if str(obj.type) == 'QRCODE' and 'first-page' in str(obj.data) :
                    if copy_nr > 0:
                        pages_by_copy.append([copy_nr_dir,page_nr])

                    copy_nr += 1
                    copy_nr_dir = "copy_"+str(copy_nr).zfill(3)
                    subdir = os.path.join(scans_dir,copy_nr_dir)
                    os.mkdir(subdir)
                    current_subdir = subdir
                    page_nr = 0


            page_nr += 1
            print(f)
            os.rename(f,current_subdir+"/"+os.path.basename(f))

    pages_by_copy.append([copy_nr_dir,page_nr])

    for copy in pages_by_copy:
        print(copy[0]+" - "+str(copy[1])+" pages")
