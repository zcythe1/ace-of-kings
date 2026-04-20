from flask import Blueprint, request, redirect, session, render_template

from extensions.gamestorage import valid_product_codes

main_bp = Blueprint('main', __name__)

@main_bp.route("/", methods=["GET", "POST"])
def index():
    error = ""
    if request.method == "POST":
        entered_key = request.form.get("key", "").strip().upper()
        matched_id = None
        for product_id, data in valid_product_codes.items():
            if data.get("key", "").upper() == entered_key:
                matched_id = product_id
                break
        if not matched_id:
            error = "Key not recognised."
        else:
            session["product_id"] = matched_id
            return redirect("/host")
    return render_template("index.html", error=error)
