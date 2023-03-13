from django import template

register = template.Library()

# @register.filter
# def getPageFromJpgPath(jpg_path):
#     split_path = jpg_path.split('/')
#     return split_path[-1].split('.')[0]
#
# @register.filter
# def getCopyAndPageFromJpgPath(jpg_path):
#     split_path = jpg_path.split('/')
#     copyPage = split_path[-2] + " page " + split_path[-1].split('_')[-1].split('.')[0]
#     return copyPage
