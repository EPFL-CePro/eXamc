#package
import matplotlib
import PIL
import numpy as np
import csv

#to import image
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import Image, ImageDraw, ImageFont

#set font     
font = ImageFont.truetype("Tests/fonts/NotoSans-Bold.ttf", 10)

with open('examc_app/scripts/param.csv') as paramfile:
    for map, coord_file, export, number_option, skip_option, start, end, special_case, draw_option in csv.reader(
            paramfile, delimiter=','):
        # read image and csv file
        image_name = 'examc_app/scripts/map/' + map
        csv_name = 'examc_app/scripts/csv/' + coord_file
        n = int(start)
        m = int(end)
        export_name = 'examc_app/scripts/export/' + export
        draw_shape = draw_option
        special_case_name = 'examc_app/scripts/csv_special_numbers/' + special_case
        # Open image file
        print("...open map file " + image_name + "...")
        image = Image.open(image_name)
        draw = ImageDraw.Draw(image)
        # Number seats for continuous numbering
        if (number_option == "continuous"):
            i = n
            with open(csv_name) as csvfile:
                print("......numbers seats......")
                for x, y in csv.reader(csvfile, delimiter=','):
                    coordx = int(x)
                    coordy = int(y)
                    string = f'{i}'
                    #check if the number is a special case and skip it if asked
                    if (number_option == "continuous" and skip_option == "skip"):
                        with open(special_case_name) as csvspecial:
                            for row in csv.reader(csvspecial, delimiter=','):
                                if (string == f'{row[0]}'):
                                    i += 1
                                    string = f'{i}'
                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    if draw_shape == "square":
                        draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                       outline='black')
                    draw.text((coordx + 1, coordy), string, fill='red', anchor='mm', font=font)
                    i += 1
                    if i > m:
                        break

                    #number seat for special case
        if (number_option == "special"):
            i = n
            with open(csv_name) as csvfile:
                print("......numbers seats......")
                for x, y in csv.reader(csvfile, delimiter=','):
                    coordx = int(x)
                    coordy = int(y)
                    string = ""
                    with open(special_case_name) as csvspecial:
                        k = 0
                        for row in csv.reader(csvspecial, delimiter=','):
                            k += 1
                            if (k == i):
                                string = f'{row[0]}'
                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    if draw_shape == "square":
                        draw.rectangle([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                       outline='black')
                    draw.text((coordx + 1, coordy), string, fill='black', anchor='mm', font=font)
                    i += 1
                    if i > m:
                        break
                    #save image
        print("...export image " + export_name + "...")
        image.save(export_name)
