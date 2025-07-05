import os
import re
import sys
import tkinter as tk
import tkinter.scrolledtext as st
import xml.etree.ElementTree as ET

from tabulate import tabulate
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk


def get_all_files(input_folder, output_folder):
    """ returns a list of tuples of in and out files"""
    
    allFiles = []
    for file_name in os.listdir(input_folder):
        if file_name.endswith('.eaf'):
            input_path = os.path.join(input_folder, file_name)
            output_path = os.path.join(output_folder, f"{os.path.splitext(file_name)[0]}.eaf")
            allFiles.append([input_path, output_path])
    
    return allFiles


def get_data(file_path):
    """ gets all REF_ANNOTATIONS out of the ELAN file
    """
    
    data = {} # get all annotations into a standard format

    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Iterate over each TIER element
    for tier in root.findall("TIER"):
        tier_type = tier.get("LINGUISTIC_TYPE_REF", "")

        # Iterate over each REF_ANNOTATION element
        for nummer, ref_annotation in enumerate(tier.findall(".//REF_ANNOTATION")):
            annotation_id = ref_annotation.get("ANNOTATION_ID", "")
            annotation_ref = ref_annotation.get("ANNOTATION_REF", "")
            annotation_value = ref_annotation.find("ANNOTATION_VALUE").text if ref_annotation.find("ANNOTATION_VALUE") is not None else ""

            # Append the extracted data as a dictionary
            data[annotation_id] = {
                #"File": file_name,
                "TIER_TYPE": tier_type,
                "ANNOTATION_ID": annotation_id,
                "ANNOTATION_REF": annotation_ref,
                "ANNOTATION_VALUE": annotation_value,
                "ANNOTATION_NUMBER": nummer,
                "RELATIVES" : [],
                #"PARENTS": [], # not needed, as the parent is in ANNOTATION_REF
                "CHILDREN": [],
                "BLOODLINE": []
            }
    return data

    
def find_children(data):
    """ find all children of a annotation
        finds other annotations which ref this one"""
    for k, v in data.items():
        parent = v["ANNOTATION_REF"]
        if parent in data:
            data[parent]["CHILDREN"].append(k)
    return data


def clean_pattern(pattern):
    """ if there is no key given, ".*" is default
    """
    if list(pattern.keys())[0] == '':
        search_type = ".*"
    else:
        search_type = list(pattern.keys())[0]
        
    search_string = list(pattern.values())[0]
    
    return search_type, search_string


def add_to_stats(v, stats, data):
    """add to statistics """
    
    if v['ANNOTATION_VALUE'] not in stats:
        stats[v['ANNOTATION_VALUE']] = {'tier': {}, 'parents': {}, 'children': {}, "count": 0}

    if v["TIER_TYPE"] not in stats[v['ANNOTATION_VALUE']]["tier"]:
        stats[v['ANNOTATION_VALUE']]["tier"][v["TIER_TYPE"]] = 0

    stats[v['ANNOTATION_VALUE']]["tier"][v["TIER_TYPE"]] += 1

    stats[v['ANNOTATION_VALUE']]["count"] += 1
    
    return stats


def grouping_stats(source):
    """ creates what will be added into a single cell in the dispay table"""
    cell_content = []
    for item, nr in source.items():
            cell_content.append(item + " " + str(nr))
    
    return "\n".join(cell_content)
    
    
def print_stats(stats):
    """ construct and print the stats table"""
    
    stats_print = [["term", "tier", "parent", 'children']] # table header
    
    for k, v in stats.items():
        
        term = k + " " + str(v["count"])
        
        tiers = grouping_stats(v['tier'])
        
        eltern = grouping_stats(v['parents'])

        kinder = grouping_stats(v['children'])

        stats_print.append([term, tiers, eltern, kinder])
    
    print ("Statistics for all files: ", )
    print(tabulate(stats_print, headers='firstrow', tablefmt='fancy_grid')) 

    
def add_item_to_stats(v, stats, item, group):
    """ for display in stats"""
            
    if item not in stats[v['ANNOTATION_VALUE']][group]:

        stats[v['ANNOTATION_VALUE']][group][item] = 0

    stats[v['ANNOTATION_VALUE']][group][item] +=1
    
    return stats

def assemble_tier_value(data, relative):
    """for display in table"""
    relative_type = data[relative]["TIER_TYPE"]
    relative_value = data[relative]["ANNOTATION_VALUE"]
    
    # in case of NoneType, we need two options
    if relative_type and relative_value:
        return relative_type + ": " + relative_value
    else:
        return " "

    
def add_to_file_table(v, stats, file_table, data):
                        
    parent = ""

    stats = add_to_stats(v, stats, data)

    target = v["TIER_TYPE"] + ": " + v["ANNOTATION_VALUE"]

    #get parents
    if v["ANNOTATION_REF"] in data:
        papa = v["ANNOTATION_REF"]
        parent = assemble_tier_value(data, papa) 
        stats = add_item_to_stats(v, stats, parent, "parents")

    # get children
    children = []

    if len(v["CHILDREN"]) > 0:

        for child in v["CHILDREN"]:
            kid = assemble_tier_value(data, child)
            stats = add_item_to_stats(v, stats, kid, "children")
            
            children.append(kid)

    file_table.append([target, parent, "\n".join(children)]) 
    
    return file_table, stats


def check_if_match(v, search_type, search_string):
    """ check if search_type and search_string match"""
    # no string no results
    if v['ANNOTATION_VALUE']:

        # filter for TIER_TYPE
        if re.fullmatch(search_type, v['TIER_TYPE']):

            # find the string or regex
            if re.fullmatch(search_string, v['ANNOTATION_VALUE']):
                return True
            
    return False


def find_string(input_folder, pattern):
    
    search_type, search_string = clean_pattern(pattern)
    
    output_text.delete("1.0", "end")
    
    stats ={} #dict for the statistical info accross all files
    
    input_folder = input_path_var.get()
    output_folder = output_folder_var.get()
    
    all_files = get_all_files(input_folder, output_folder)
    
    for file_in, file_out in all_files:

        print ("\n", " ", file_in, "\n")

        file_table = [['term', 'parent', 'children']]
        
        data = get_data(file_in)
        
        data = find_children(data)
        
        for k, v in data.items():
            
            match_check = check_if_match(v, search_type, search_string)
            
            if match_check:
                file_table, stats = add_to_file_table(v, stats, file_table, data)
                
        print(tabulate(file_table, headers='firstrow', tablefmt='fancy_grid'))   
    
    print_stats(stats)
    
    output_text.see("1.0")

    
    
#input_folder = "./test_out"
#output_folder = "./test_out"

#find_string(input_folder, {"lexical-unit": "n.*"})
#find_string(input_folder, {"": "n.*"})


def find_match(anno):
    """ get all family members of a annotation into a list, itself, it's children, it's parents"""
    anno_id = anno["ANNOTATION_ID"]
    anno_ref = anno["ANNOTATION_REF"]
    anno_children = anno["CHILDREN"]
    anno_list = [anno["ANNOTATION_ID"], anno["ANNOTATION_REF"]]
    for x in anno_children:
        anno_list.append(x)
    return anno_list


def three_rows_filled(match1, match2, match3):
    """ all three rows are filled"""
    change_list = []
    partners = []
    
    for third in match3:
        list3 = find_match(third)
        
        for second in match2:
            list2 = find_match(second)
            
            for first in match1:
                list1 = find_match(first)
                
                common_all = set(list1) & set(list2) & set(list3)

                if common_all:
                    partners.append([first,second,third])
                    change_list.append(third["ANNOTATION_ID"])

    return change_list, partners


def two_bottom_rows_filled(match2, match3):
    """ the bottom two rows are loaded"""
    change_list = []
    partners = []
    
    for third in match3:
        list3 = find_match(third)
        
        for second in match2:
            list2 = find_match(second)

            common_all = set(list2) & set(list3)
                        
            if common_all:
                partners.append([second,third])
                change_list.append(third["ANNOTATION_ID"])
                
    return change_list, partners


def top_bottom_rows_filled(match1, match3):
    """ the bottom two rows are loaded"""
    change_list = []
    partners = []
    
    for third in match3:
        list3 = find_match(third)
        
        for first in match1:
            list1 = find_match(first)

            common_all = set(list1) & set(list3)
                        
            if common_all:
                partners.append([first,third])
                change_list.append(third["ANNOTATION_ID"])
                
    return change_list, partners


def one_rows_filled(match3):
    """ Only the last row is filled with terms
    """
    change_list = []
    partners = []
    for third in match3:
        
        list3 = find_match(third)

        common_all = set(list3)

        # Results
        if common_all:
            #print(f"All lists share at least one ID: {common_all}")
            partners.append([third])
            change_list.append(third["ANNOTATION_ID"])

    return change_list, partners

def process_files(mode):
    
    output_text.delete("1.0", "end")
    
    input_folder = input_path_var.get()
    output_folder = output_folder_var.get()
    
    key1 = key1_var.get()
    word1 = word1_var.get()
    
    key2 = key2_var.get()
    word2 = lexical_unit1_var.get()
    
    key3 = key3_var.get()
    word3 = pos1_var.get()
    replacer3 = pos2_var.get()
    

    all_files = get_all_files(input_folder, output_folder)
    
    for file_in, file_out in all_files:
        
        change_list = []
        
        match1 = []
        match2 = []
        match3 = []

        print ("\n", " ", file_in, "\n")
        
        data = get_data(file_in)

        data = find_children(data)
        
        for k, v in data.items():

            match_check1 = check_if_match(v, key1, word1)
            match_check2 = check_if_match(v, key2, word2)
            match_check3 = check_if_match(v, key3, word3)
            
            
            if match_check1:
                match1.append(v)
            
            if match_check2:
                match2.append(v)
            
            if match_check3:
                match3.append(v)
            
            
        partners = []
        
        # all three rows are filled
        if (len(key1 + word1) > 0) and (len(key2 + word2) > 0):
            
            change_list, partners = three_rows_filled(match1, match2, match3)

        # bottom two rows are filled
        elif (len(key2 + word2) > 0):
            change_list, partners = two_bottom_rows_filled(match2, match3)
        
        # top and bottom rows are filled
        elif (len(key1 + word1) > 0):
            change_list, partners = top_bottom_rows_filled(match1, match3)
        
        else:
            change_list, partners = one_rows_filled(match3)
            
        if mode == "replace":
            write_to_file(change_list, file_in, file_out, word3, replacer3)
        
        if mode == "find_only":
            
            for group in partners:
                out_print = []
                for each in group:
                    out_print.append("  " + each["TIER_TYPE"] + ": \t\t\t\t" +  each["ANNOTATION_VALUE"])
            
                print ("\n".join(out_print))
                print ("----------------------")
    output_text.see("1.0")
        
def write_to_file(change_list, file_path, output_path, old, new):
    #for each in matches:
    #    print (each)

    # replace all matching annotations based on the replacement dictionary
    tree = ET.parse(file_path)

    root = tree.getroot()

    # Iterate over each TIER element
    for tier in root.findall("TIER"):
        tier_type = tier.get("LINGUISTIC_TYPE_REF", "")

        # Iterate over each REF_ANNOTATION element
        for ref_annotation in tier.findall(".//REF_ANNOTATION"):
            annotation_id = ref_annotation.get("ANNOTATION_ID", "")
            annotation_value = ref_annotation.find("ANNOTATION_VALUE").text if ref_annotation.find("ANNOTATION_VALUE") is not None else ""

            infos = []

            if annotation_id in change_list:
                
                ref_annotation.find("ANNOTATION_VALUE").text = new

                print("   ", ", ".join(infos), ":: ", tier_type, annotation_id, annotation_value, " --> ",new)




    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    
    output_text.see("1.0")
            
                            
#process_files()  


# Redirect standard output and error to the Text widget
class TextRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
    
    def write(self, text):
        
        self.text_widget.insert("end", text)
        #self.text_widget.see("end")  # Auto-scroll to the bottom

    def flush(self):  # Needed for some interactive environments
        pass

# Function to select a folder
def select_folder(var):
    folder = filedialog.askdirectory()
    if folder:
        var.set(folder)


# USER INTERFACE -------------------------------------------------------------------------------------------
        
def print_instructions():
    
    output_text.delete("1.0", "end")
    
    print (""" 

 INSTRUCTIONS:
 
 
 
  1. Define input and output folders
    
    !!! IF INPUT AND OUTPUT FOLDER ARE THE SAME ALL FILES ARE OVERWRITTEN !!!
 
 
 
 2. Look for ANNOTATIONS in any Tier Type. 
 
    FIND: All annotations matching your search pattern are displayed 
 
    REPLACE: All annotations in cell x gets replaced with content of cell y
 
 
    
     Tier Type:      Look for:
   ╭―――――――――――――――――――――――――――――╮
   │ [        ]      [        ]  │  
   │                             │
   │ [        ]      [        ]  │
   │                             │
   │ [        ]      [    x   ]  │        [   y   ]
   ╰―――――――――――――――――――――――――――――╯ 
     
     
    THIS IS NOT A TOY! ALLWAYS BACK UP YOUR DATA BEFORE USE!
    
    
    IF you have any questions contact: barth.wolf@gmail.com
    
      

""")
    
    
# Main Tkinter window
root = tk.Tk()
root.title("EAF File Processor SEARCH & REPLACE 3000")

# Variables
current_dir = os.getcwd()
input_path_var = tk.StringVar(value=current_dir)
output_folder_var = tk.StringVar(value=current_dir)


key1_var = tk.StringVar(value="words")
key2_var = tk.StringVar(value="lexical-unit")
key3_var = tk.StringVar(value="POS")

word1_var = tk.StringVar(value="Ngau")
word2_var = tk.StringVar(value="")
lexical_unit1_var = tk.StringVar(value="ngau")
lexical_unit2_var = tk.StringVar(value="")
pos1_var = tk.StringVar(value="Pronoun")
pos2_var = tk.StringVar(value="Pronoun")


# Input path selection
tk.Label(root, text="Input Path:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
tk.Entry(root, textvariable=input_path_var, width=100).grid(row=0, column=1, padx=5, pady=5, sticky="e")
tk.Button(root, text="Browse", width=15, command=lambda: select_folder(input_path_var)).grid(row=0, column=2, padx=5, pady=5)


# Output folder selection
tk.Label(root, text="Output Folder:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
tk.Entry(root, textvariable=output_folder_var, width=100).grid(row=1, column=1, padx=5, pady=5, sticky="e")
tk.Button(root, text="Browse", width=15, command=lambda: select_folder(output_folder_var)).grid(row=1, column=2, padx=5, pady=5)


# Search section
tk.Label(root, text="    Tier Type:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
tier_type_var = tk.StringVar()  # Variable to hold the tier type input
tk.Entry(root, textvariable=tier_type_var, width=20).grid(row=2, column=0, padx=5, pady=5, sticky="e")

tk.Label(root, 
         text="                                                                                           Search String:").grid(row=2, column=1, sticky="w", padx=5, pady=5)
search_string_var = tk.StringVar()  # Variable to hold the search string
tk.Entry(root, textvariable=search_string_var, width=40).grid(row=2, column=1, padx=5, pady=5, sticky="e")

tk.Button(root, text="Search", width=15, command=lambda: find_string(input_path_var.get(), 
                                                           {tier_type_var.get(): search_string_var.get()})).grid(row=2, column=2, padx=5, pady=5)


# Horizontal line below row 2
separator = ttk.Separator(root, orient='horizontal')
separator.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)


tk.Label(root, text=" REPLACE ANNOTATIONS").grid(row=4, column=0, sticky="w", columnspan=3, padx=5, pady=5)

tk.Button(root, text="Instructions",  bg='white', width=15, command=lambda: print_instructions()).grid(row=4, column=2, sticky="e", padx=10, pady=10)


# Labels for columns
tk.Label(root, text=" Tier Type:").grid(row=5, column=0, sticky="w", padx=5, pady=5)
tk.Label(root, text="Look for:").grid(row=5, column=1, sticky="w", padx=5, pady=5)
#tk.Label(root, text="Replace with:").grid(row=4, column=1, sticky="e", padx=5, pady=5)


#first row of data
tk.Entry(root, textvariable=key1_var, width=35).grid(row=6, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=word1_var, width=35).grid(row=6, column=1, padx=5, pady=5, sticky="w")


# second row of data
tk.Entry(root, textvariable=key2_var, width=35).grid(row=7, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=lexical_unit1_var, width=35).grid(row=7, column=1, padx=5, pady=5, sticky="w")
tk.Label(root, text="Replace with:                                              ").grid(row=6, column=1, sticky="e", padx=5, pady=5)


# third row of data
tk.Entry(root, textvariable=key3_var, width=35).grid(row=8, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=pos1_var, width=35, bg='papaya whip').grid(row=8, column=1, padx=5, pady=5, sticky="w")
tk.Entry(root, textvariable=pos2_var, width=35, bg='papaya whip').grid(row=8, column=1, padx=5, pady=5, sticky="e")


# Process button
tk.Button(root, text="Find",  bg='orange', width=15, command=lambda: process_files("find_only")).grid(row=9, column=0, columnspan=3, pady=10)
tk.Button(root, text="Replace",  bg='red', width=15, command=lambda: process_files('replace')).grid(row=9, column=2, columnspan=3, pady=10)

root.grid_rowconfigure(10, weight=1)  # Allow row 9 to grow/shrink
# Output Textarea
output_text = st.ScrolledText(root, height=25, width=120, wrap="word")
output_text.grid(row=10, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
output_text.configure(state="normal")


# Redirect stdout and stderr to the Text widget
sys.stdout = TextRedirector(output_text)
sys.stderr = TextRedirector(output_text)


# Run the Tkinter event loop
root.mainloop()  