from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.colors import CMYKColor, black

# Constants
MM_TO_POINTS = 2.83464567
# Margins and spacing from the Javascript file
BOX_AREA_HORIZ_MARGIN_TOTAL = 198.425197
BOX_AREA_VERT_MARGIN_TOTAL = 198.425197 # Assuming same as horizontal for consistency with JS box calc
X_REF_START_OFFSET = 42.519685 # Left margin to first box / right of Y labels
Y_REF_START_OFFSET = 42.519685 # Bottom margin to first box / below X labels
BOX_SPACING = 11.3385827     # Gap between boxes

# CMYK definitions for "spot" colours (as per JS initializeSwatchPallette)
CMYK_DEFINITIONS = {
    "Cyan": (1.0, 0.0, 0.0, 0.0), # Process Cyan
    "Magenta": (0.0, 1.0, 0.0, 0.0), # Process Magenta
    "Yellow": (0.0, 0.0, 1.0, 0.0), # Process Yellow
    "Black": (0.0, 0.0, 0.0, 1.0), # Process Black
    "Orange": (0.0, 0.7, 0.7, 0.0), # M=70, Y=70
    "Violet": (0.7, 0.7, 0.0, 0.0), # C=70, M=70
    "Grey": (0.0, 0.0, 0.0, 0.7)  # K=70 (for PANTONE Cool Gray 10 C)
}

def get_int_input(prompt_text, default_val_str, min_val=None, max_val=None):
    """Gets an integer input from the user with validation."""
    while True:
        try:
            val_str = input(f"{prompt_text} (default: {default_val_str}): ") or default_val_str
            val_int = int(val_str)
            if min_val is not None and val_int < min_val:
                print(f"Value must be at least {min_val}.")
                continue
            if max_val is not None and val_int > max_val:
                print(f"Value must be no more than {max_val}.")
                continue
            return val_int
        except ValueError:
            print("Invalid input. Please enter a whole number.")

def get_colour_input(colour_name, default_tint_str="0"):
    """Gets colour tint input, allowing 'v' for variable."""
    while True:
        val_str = input(f"Please enter % of {colour_name} (0-100), or 'v' if variable (default: {default_tint_str}): ") or default_tint_str
        if val_str.lower() == 'v':
            return 'v'
        try:
            val_int = int(val_str)
            if 0 <= val_int <= 100:
                return val_int
            else:
                print("Percentage must be between 0 and 100.")
        except ValueError:
            print("Invalid input. Please enter a number or 'v'.")

def overprint_layer(current_cmyk_percent, layer_cmyk_base, layer_tint_percent):
    """
    Applies a new CMYK layer with tint on top of an existing CMYK colour.
    Colours are additive, capped at 100%.
    current_cmyk_percent: tuple (c,m,y,k) with values 0-100
    layer_cmyk_base: tuple (c,m,y,k) for the layer at 100% tint, values 0.0-1.0
    layer_tint_percent: float tint value 0-100 for the layer
    """
    base_c, base_m, base_y, base_k = current_cmyk_percent
    layer_def_c, layer_def_m, layer_def_y, layer_def_k = layer_cmyk_base
    
    tint_factor = layer_tint_percent / 100.0
    
    add_c = layer_def_c * tint_factor * 100
    add_m = layer_def_m * tint_factor * 100
    add_y = layer_def_y * tint_factor * 100
    add_k = layer_def_k * tint_factor * 100
            
    new_c = min(100, base_c + add_c)
    new_m = min(100, base_m + add_m)
    new_y = min(100, base_y + add_y)
    new_k = min(100, base_k + add_k)
    return (new_c, new_m, new_y, new_k)

def create_swatch_pdf(filename="colour_swatch_output.pdf"):
    """Main function to create the PDF swatch chart."""

    print("--- Document Setup ---")
    docwidthmm = get_int_input("Please enter document width in millimeters", "444")
    docheightmm = get_int_input("Please enter document height in millimeters", "316")

    docwidthpts = docwidthmm * MM_TO_POINTS
    docheightpts = docheightmm * MM_TO_POINTS

    c = canvas.Canvas(filename, pagesize=(docwidthpts, docheightpts))

    variable_colours_data = [] # To store (name, median_tint, actual_start_val, index_in_cmyk_defs_keys)

    print("\n--- Colour Percentages ---")
    print("Please enter the percentage of each colour, or 'v' if the colour will be variable (only 2 may be selected)")

    colour_inputs = {}
    colour_order = ["Cyan", "Magenta", "Yellow", "Black", "Orange", "Violet", "Grey"]

    for colour_name in colour_order:
        default_val = "0"
        # Mimic PDF example: Dark Green, Yellow=30%, Cyan & Black variable
        if colour_name == "Yellow": default_val = "30"
        if colour_name == "Cyan": default_val = "v"
        if colour_name == "Black": default_val = "v"


        tint_input = get_colour_input(colour_name, default_val)
        colour_inputs[colour_name] = {"value": tint_input, "median": 0}

        if tint_input == 'v':
            if len(variable_colours_data) < 2:
                median_default = "50"
                if len(variable_colours_data) == 0 and colour_name == "Cyan": median_default = "65" # From PDF example C=50-80, median ~65
                if len(variable_colours_data) == 1 and colour_name == "Black": median_default = "85" # From PDF example K=70-100, median ~85

                median_tint = get_int_input(f"{colour_name} will be variable. Enter median % for {colour_name}", median_default, 0, 100)
                colour_inputs[colour_name]["median"] = median_tint
                variable_colours_data.append({"name": colour_name, "median_tint": median_tint, "start_val": 0})
            else:
                print(f"Already selected 2 variable colours. Treating {colour_name} as 0%.")
                colour_inputs[colour_name]["value"] = 0

    step_val = get_int_input("\nPlease enter a number between 1 and 9 for the % gap between swatches", "3", 1, 9)

    # Calculate start values for variable swatches
    for var_col_data in variable_colours_data:
        median = var_col_data["median_tint"]
        start_val = median - (step_val * 5)
        
        # Adjust if out of bounds (0-100)
        if (step_val * 5) + median > 100:
            start_val = 100 - (step_val * 10)
        if (median - (step_val * 5)) < 0:
            start_val = 0
        var_col_data["start_val"] = start_val

    # Set width and height of swatch boxes
    box_width = (docwidthpts - BOX_AREA_HORIZ_MARGIN_TOTAL) / 11
    box_height = (docheightpts - BOX_AREA_VERT_MARGIN_TOTAL) / 11
    
    # --- Drawing Grid ---
    for k_row in range(11): # 0 to 10 (Y-axis iteration - for rows)
        for i_col in range(11): # 0 to 10 (X-axis iteration - for columns)
            
            # Initial CMYK for the cell (all components 0-100)
            current_cell_cmyk_percent = [0.0, 0.0, 0.0, 0.0]

            # Layer 1: Base static CMYK process colours
            for colour_name in ["Cyan", "Magenta", "Yellow", "Black"]:
                if colour_inputs[colour_name]["value"] != 'v':
                    tint_val = colour_inputs[colour_name]["value"]
                    if tint_val > 0:
                        # Directly set base CMYK, as these are the primary components
                        if colour_name == "Cyan": current_cell_cmyk_percent[0] = min(100, current_cell_cmyk_percent[0] + tint_val)
                        elif colour_name == "Magenta": current_cell_cmyk_percent[1] = min(100, current_cell_cmyk_percent[1] + tint_val)
                        elif colour_name == "Yellow": current_cell_cmyk_percent[2] = min(100, current_cell_cmyk_percent[2] + tint_val)
                        elif colour_name == "Black": current_cell_cmyk_percent[3] = min(100, current_cell_cmyk_percent[3] + tint_val)
            
            # Layers 2, 3, 4: Static "spot" colours (Orange, Violet, Grey)
            for spot_colour_name in ["Orange", "Violet", "Grey"]:
                if colour_inputs[spot_colour_name]["value"] != 'v':
                    tint_val = colour_inputs[spot_colour_name]["value"]
                    if tint_val > 0:
                        layer_cmyk_def = CMYK_DEFINITIONS[spot_colour_name]
                        current_cell_cmyk_percent = overprint_layer(current_cell_cmyk_percent, layer_cmyk_def, tint_val)

            # Layer 5: Variable Colour 1 (X-axis)
            if len(variable_colours_data) > 0:
                var_col1_data = variable_colours_data[0]
                var_col1_name = var_col1_data["name"]
                var_col1_cmyk_def = CMYK_DEFINITIONS[var_col1_name]
                # Ensure tint value does not exceed 100 or go below 0 after steps
                current_tint_var1 = max(0, min(100, var_col1_data["start_val"] + i_col * step_val))
                current_cell_cmyk_percent = overprint_layer(current_cell_cmyk_percent, var_col1_cmyk_def, current_tint_var1)

            # Layer 6: Variable Colour 2 (Y-axis)
            if len(variable_colours_data) > 1:
                var_col2_data = variable_colours_data[1]
                var_col2_name = var_col2_data["name"]
                var_col2_cmyk_def = CMYK_DEFINITIONS[var_col2_name]
                 # Ensure tint value does not exceed 100 or go below 0 after steps
                current_tint_var2 = max(0, min(100, var_col2_data["start_val"] + k_row * step_val))
                current_cell_cmyk_percent = overprint_layer(current_cell_cmyk_percent, var_col2_cmyk_def, current_tint_var2)

            # Final CMYK for reportlab (0.0 to 1.0)
            final_c = current_cell_cmyk_percent[0] / 100.0
            final_m = current_cell_cmyk_percent[1] / 100.0
            final_y = current_cell_cmyk_percent[2] / 100.0
            final_k = current_cell_cmyk_percent[3] / 100.0
            
            c.setFillColor(CMYKColor(final_c, final_m, final_y, final_k))

            # Calculate box position (ReportLab origin is bottom-left)
            # JS yRef is top of rectangle and increases upwards.
            # JS xRef is left of rectangle and increases rightwards.
            # X_REF_START_OFFSET and Y_REF_START_OFFSET are from bottom-left of grid area.
            box_x_bl = X_REF_START_OFFSET + i_col * (box_width + BOX_SPACING)
            box_y_bl = Y_REF_START_OFFSET + k_row * (box_height + BOX_SPACING)
            
            c.rect(box_x_bl, box_y_bl, box_width, box_height, fill=1, stroke=0)

    # --- Title ---
    title_str = input("Please enter text for title (colour info added automatically): ") or "Swatch Chart"
    full_title = ""
    if colour_inputs["Orange"]["value"] != 'v' and colour_inputs["Orange"]["value"] > 0 or \
       colour_inputs["Violet"]["value"] != 'v' and colour_inputs["Violet"]["value"] > 0 or \
       colour_inputs["Grey"]["value"] != 'v' and colour_inputs["Grey"]["value"] > 0:
        full_title += "VOG "
    full_title += title_str

    for name in colour_order:
        val = colour_inputs[name]["value"]
        if val != 'v' and val > 0:
            full_title += f" {name}={val}%"
    
    c.setFillColor(black) # Default text to black
    c.setFont("Helvetica", 10)
    title_x = X_REF_START_OFFSET # JS: TitleText.left = 42.519685
    title_y = docheightpts - 15  # JS: TitleText.top = docheightpts - 15
    c.drawString(title_x, title_y, full_title.strip())
    
    # --- Labels ---
    # X-axis labels (values and name)
    # JS XText.top = 42; XTextCol.top = 27;
    # These are from page top.
    label_y_x_values = docheightpts - 42
    label_y_x_name = docheightpts - 27

    if len(variable_colours_data) > 0:
        var_col1_data = variable_colours_data[0]
        start_val_x_axis = var_col1_data["start_val"]
        
        # X-axis Colour Name
        c.drawCentredString(docwidthpts / 2, label_y_x_name, var_col1_data["name"])
        
        # X-axis Percentage Values
        for i_col in range(11):
            label_val = max(0, min(100, start_val_x_axis + i_col * step_val))
            # JS Xstart (left of text frame)
            text_x = X_REF_START_OFFSET + (i_col * (box_width + BOX_SPACING)) + (box_width / 2) # Centred on box
            c.drawCentredString(text_x, label_y_x_values, str(int(round(label_val))))

    # Y-axis labels (values and name)
    # JS YText.left = 22.519685; YTextCol.left = 7;
    label_x_y_values = 22.519685
    label_x_y_name = 7

    if len(variable_colours_data) > 1:
        var_col2_data = variable_colours_data[1]
        start_val_y_axis = var_col2_data["start_val"]

        # Y-axis Colour Name (rotated)
        c.saveState()
        c.translate(label_x_y_name, docheightpts / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, var_col2_data["name"]) # Draw at new (0,0)
        c.restoreState()

        # Y-axis Percentage Values
        # JS Ystart = 52.519685 (top of text frame), increases for subsequent labels (moves down page)
        # This means higher percentage values are lower on the page.
        js_y_text_top_start = 52.519685 
        for k_row in range(11): # For labels, iterate consistent with display
            label_val = max(0, min(100, start_val_y_axis + k_row * step_val))
            
            # JS YText.top = Ystart; Ystart increments. This is top of text frame.
            # For ReportLab, y is bottom of string.
            # We want the labels to align with the boxes.
            # text_y_rl_bottom = Y_REF_START_OFFSET + k_row * (box_height + BOX_SPACING) + (box_height / 2) - (font_size / 2 approx)
            # Let's align with center of box height using the JS left margin for X
            text_y = Y_REF_START_OFFSET + (k_row * (box_height + BOX_SPACING)) + (box_height/2) # Center of box
            
            # To match JS's downward increasing values from a top Y starting point:
            # The JS effectively means the label for k_row=0 (bottom row of swatches) is start_val_y_axis.
            # The label for k_row=10 (top row of swatches) is start_val_y_axis + 10 * step_val.
            # So the displayed labels should go upwards if k_row increases upwards.
            
            # The PDF example (Dark Green.pdf) shows Y-axis values (70..100) increasing upwards.
            # The JS script's Y-axis text label loop takes startValY (e.g. 70), prints it, then increments startValY.
            # It positions these using YText.top = Ystart, where Ystart *increases*, meaning labels go *down* the page.
            # So "70" is highest, "73" below it, etc. This Python code will match that JS logic.
            
            # Use k_row to determine which Ystart value from JS logic to use.
            # The JS Ystart loop for labels is separate from box drawing, but implies this:
            # Label 0 (bottom swatch) has tint startValY + 0*step
            # Label 10 (top swatch) has tint startValY + 10*step
            # The JS places text at YText.top = Ystart_js; where Ystart_js = 52.519685 + label_index * (boxHeight + spacing)
            # So label_index 0 is at Y_top = 52.5..., label_index 10 is at Y_top = 52.5... + 10*(H+S)
            # This means text for start_val_y_axis (e.g. 70) is at highest Y (top of page). Text for start_val_y_axis + 10*step is lowest.
            
            # For correct vertical alignment with boxes, and matching JS top-down value display:
            # We want the label for the (10-k_row)-th value in the JS sequence,
            # placed at the k_row-th box vertical position.
            # No, simpler: the JS prints values `startValY, startValY+step, ...`
            # at positions `Y_js_top_0, Y_js_top_1, ...` where `Y_js_top_i` moves down.
            # So, row k_row (0=bottom, 10=top) gets label `startValY + k_row * stepVal`.
            # This matches the actual tint of the row.
            # The JS positioning `YText.top = Ystart` (where `Ystart` increases for subsequent labels) means that
            # the first label (value `startValY`) is at `docheightpts - js_y_text_top_start`.
            # The second label (value `startValY + stepVal`) is at `docheightpts - (js_y_text_top_start + box_height + BOX_SPACING)`.
            # This means lower `k_row` (bottom of grid) should have higher `Ystart_js_equivalent` if mapping bottom-up.
            
            # Let's follow the provided PDF example for Y-axis label *direction* (values increase upwards)
            # as it's more conventional, but use JS *coordinates* for placement.
            # The JS logic for Y labels is: value `S+i*step` at `Y_top = Y_base_top + i*(boxH+gap)`.
            # This means `S` is at top-most label spot, `S+step` below it.
            # If we want values to increase upwards (like PDF):
            # Row k (0=bottom, 10=top) should have label `start_val_y_axis + k_row * stepVal`.
            # Position it at:
            y_coord_for_label_js_top = js_y_text_top_start + (10 - k_row) * (box_height + BOX_SPACING) # Higher k_row -> smaller Y_top -> higher on page
            text_y_rl = docheightpts - y_coord_for_label_js_top # Convert JS top to RL bottom for string
            # Adjust for font baseline, typically text is drawn with y as baseline.
            # For centering vertically in an approximate way:
            font_size_approx = 8 # Assuming label font size
            text_y_rl_centered = docheightpts - y_coord_for_label_js_top - font_size_approx / 2


            current_label_val_for_row = max(0, min(100, start_val_y_axis + k_row * step_val))
            # The JS positions `YText.contents = startValY` (which increments) at `YText.top = Ystart` (which also increments, moving down).
            # So value `V0` is at `Ytop0`, `V1` at `Ytop1` (lower).
            # We want to place label `start_val_y_axis + k_row * stepVal` (which is the tint of row k_row)
            # at a Y position that corresponds to the JS's placement scheme.
            # JS places the k-th label in its sequence (0th label is startValY) at top Y_js_text_top_start + k * (box_height + BOX_SPACING)
            # So if our k_row is 0 (bottom), we want the JS label that corresponds to the bottom-most position.
            # The JS label sequence is `L_0, L_1, ..., L_10` where `L_i = start_val_y_axis + i * step_val`.
            # These are placed at `YTop_0, YTop_1, ..., YTop_10` where `YTop_i = js_y_text_top_start + i * (box_height + BOX_SPACING)`.
            # So `L_i` goes with `YTop_i`.
            # We are drawing row `k_row`. Its value is `val_k_row = start_val_y_axis + k_row * step_val`. This is `L_k_row`.
            # Its Y position should be `YTop_k_row`.
            y_top_for_this_label = js_y_text_top_start + k_row * (box_height + BOX_SPACING)
            final_y_rl = docheightpts - y_top_for_this_label # Anchor point for ReportLab (bottom of text)
                                                            # If font size is F, text will span [final_y_rl, final_y_rl+F]
            
            c.setFont("Helvetica", 8) # Smaller font for axis values
            c.drawRightString(label_x_y_values, final_y_rl - (font_size_approx/2), str(int(round(current_label_val_for_row))))


    c.save()
    print(f"\nPDF '{filename}' created successfully.")

if __name__ == '__main__':
    create_swatch_pdf()