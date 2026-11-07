from dataclasses import dataclass
import json
import sys




@dataclass
class RectAndField:
    rect: list[float]
    rect_type: str
    field: dict


def get_bounding_box_messages(fields_json_stream, pdf_heights=None) -> list[str]:
    """pdf_heights: {page_number: height in points}, needed for pages in image coordinates."""
    messages = []
    fields = json.load(fields_json_stream)
    pages = {p["page_number"]: p for p in fields.get("pages", [])}

    def entry_height_in_points(field, rect):
        """Font sizes are points; image-coordinate boxes are pixels. None if it cannot be converted."""
        height = rect[3] - rect[1]
        page = pages.get(field["page_number"], {})
        if "image_height" not in page:
            return height
        if not pdf_heights or field["page_number"] not in pdf_heights:
            return None
        return height * pdf_heights[field["page_number"]] / page["image_height"]

    messages.append(f"Read {len(fields['form_fields'])} fields")

    def rects_intersect(r1, r2):
        disjoint_horizontal = r1[0] >= r2[2] or r1[2] <= r2[0]
        disjoint_vertical = r1[1] >= r2[3] or r1[3] <= r2[1]
        return not (disjoint_horizontal or disjoint_vertical)

    rects_and_fields = []
    for f in fields["form_fields"]:
        rects_and_fields.append(RectAndField(f["label_bounding_box"], "label", f))
        rects_and_fields.append(RectAndField(f["entry_bounding_box"], "entry", f))

    has_error = False
    has_unchecked_height = False
    for i, ri in enumerate(rects_and_fields):
        for j in range(i + 1, len(rects_and_fields)):
            rj = rects_and_fields[j]
            if ri.field["page_number"] == rj.field["page_number"] and rects_intersect(ri.rect, rj.rect):
                has_error = True
                if ri.field is rj.field:
                    messages.append(f"FAILURE: intersection between label and entry bounding boxes for `{ri.field['description']}` ({ri.rect}, {rj.rect})")
                else:
                    messages.append(f"FAILURE: intersection between {ri.rect_type} bounding box for `{ri.field['description']}` ({ri.rect}) and {rj.rect_type} bounding box for `{rj.field['description']}` ({rj.rect})")
                if len(messages) >= 20:
                    messages.append("Aborting further checks; fix bounding boxes and try again")
                    return messages
        if ri.rect_type == "entry":
            if "entry_text" in ri.field:
                font_size = ri.field["entry_text"].get("font_size", 14)
                entry_height = entry_height_in_points(ri.field, ri.rect)
                if entry_height is None:
                    has_unchecked_height = True
                elif entry_height < font_size:
                    has_error = True
                    messages.append(f"FAILURE: entry bounding box height ({entry_height}) for `{ri.field['description']}` is too short for the text content (font size: {font_size}). Increase the box height or decrease the font size.")
                    if len(messages) >= 20:
                        messages.append("Aborting further checks; fix bounding boxes and try again")
                        return messages

    if has_unchecked_height:
        messages.append("WARNING: entry heights in image coordinates were not checked against the font size; "
                        "pass the PDF as a second argument to convert them to points")
    if not has_error:
        messages.append("SUCCESS: All bounding boxes are valid")
    return messages

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: check_bounding_boxes.py [fields.json] [input.pdf, required for image coordinates]")
        sys.exit(1)
    pdf_heights = None
    if len(sys.argv) == 3:
        from pypdf import PdfReader
        # Displayed height: a page rotated 90/270 is rendered with the MediaBox width as its height.
        pdf_heights = {i + 1: float(p.mediabox.width if p.rotation % 180 == 90 else p.mediabox.height)
                       for i, p in enumerate(PdfReader(sys.argv[2]).pages)}
    with open(sys.argv[1]) as f:
        messages = get_bounding_box_messages(f, pdf_heights)
    for msg in messages:
        print(msg)
