import json
import sys

from pypdf import PdfReader, PdfWriter

from extract_form_field_info import get_field_info, get_full_annotation_field_id
from _replace_write import refuse_linked_input, replacing




def fill_pdf_fields(input_pdf_path: str, fields_json_path: str, output_pdf_path: str):
    refuse_linked_input(input_pdf_path)
    refuse_linked_input(fields_json_path)
    with open(fields_json_path) as f:
        fields = json.load(f)
    reader = PdfReader(input_pdf_path)

    has_error = False
    field_info = get_field_info(reader)
    fields_by_ids = {f["field_id"]: f for f in field_info}
    for field in fields:
        existing_field = fields_by_ids.get(field["field_id"])
        if not existing_field:
            has_error = True
            print(f"ERROR: `{field['field_id']}` is not a valid field ID")
        elif field["page"] != existing_field["page"]:
            has_error = True
            print(f"ERROR: Incorrect page number for `{field['field_id']}` (got {field['page']}, expected {existing_field['page']})")
        else:
            if "value" in field:
                err = validation_error_for_field_value(existing_field, field["value"])
                if err:
                    print(err)
                    has_error = True
    if has_error:
        sys.exit(1)

    writer = PdfWriter(clone_from=reader)
    # A field can have widgets on several pages (e.g. a name repeated in each header); fill them all.
    widget_pages = {}
    for index, page in enumerate(writer.pages):
        for ann in page.get("/Annots") or []:
            widget_pages.setdefault(get_full_annotation_field_id(ann.get_object()), set()).add(index)
    values_by_page = {}
    for field in fields:
        if "value" in field:
            for index in widget_pages.get(field["field_id"], {field["page"] - 1}):
                values_by_page.setdefault(index, {})[field["field_id"]] = field["value"]
    for index, field_values in sorted(values_by_page.items()):
        writer.update_page_form_field_values(writer.pages[index], field_values, auto_regenerate=False)

    writer.set_need_appearances_writer(True)
    
    with replacing(output_pdf_path) as tmp, open(tmp, "wb") as f:
        writer.write(f)


def validation_error_for_field_value(field_info, field_value):
    field_type = field_info["type"]
    field_id = field_info["field_id"]
    if field_type == "checkbox":
        checked_val = field_info["checked_value"]
        unchecked_val = field_info["unchecked_value"]
        if field_value != checked_val and field_value != unchecked_val:
            return f'ERROR: Invalid value "{field_value}" for checkbox field "{field_id}". The checked value is "{checked_val}" and the unchecked value is "{unchecked_val}"'
    elif field_type == "radio_group":
        option_values = [opt["value"] for opt in field_info["radio_options"]]
        if field_value not in option_values:
            return f'ERROR: Invalid value "{field_value}" for radio group field "{field_id}". Valid values are: {option_values}' 
    elif field_type == "choice":
        choice_values = [opt["value"] for opt in field_info["choice_options"]]
        # A multi-select list takes a list of options; pypdf writes it as an array in /V.
        values = field_value if field_info.get("multi_select") and isinstance(field_value, list) else [field_value]
        # An editable combo box takes any text, not only its options (PDF 32000-1, 12.7.4.4).
        if field_info.get("editable") and isinstance(field_value, str):
            return None
        if any(value not in choice_values for value in values):
            return f'ERROR: Invalid value "{field_value}" for choice field "{field_id}". Valid values are: {choice_values}'
    return None


def monkeypatch_pydpf_method():
    from pypdf.generic import DictionaryObject
    from pypdf.constants import FieldDictionaryAttributes

    original_get_inherited = DictionaryObject.get_inherited

    def patched_get_inherited(self, key: str, default = None):
        result = original_get_inherited(self, key, default)
        if key == FieldDictionaryAttributes.Opt:
            if isinstance(result, list) and all(isinstance(v, list) and len(v) == 2 for v in result):
                result = [r[0] for r in result]
        return result

    DictionaryObject.get_inherited = patched_get_inherited


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: fill_fillable_fields.py [input pdf] [field_values.json] [output pdf]")
        sys.exit(1)
    monkeypatch_pydpf_method()
    input_pdf = sys.argv[1]
    fields_json = sys.argv[2]
    output_pdf = sys.argv[3]
    fill_pdf_fields(input_pdf, fields_json, output_pdf)
