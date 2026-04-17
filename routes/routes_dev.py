from flask import Blueprint, request, redirect, session, render_template
from werkzeug.security import check_password_hash

from config import *
from extensions.gamestorage import valid_product_codes

dev_bp = Blueprint('dev', __name__)

@dev_bp.route("/host-dev", methods=["GET", "POST"])
def host_dev():
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["product_id"] = "dev"
            valid_product_codes["dev"] = {"used": False}
            return redirect("/host")
        else:
            error = "Wrong password."
    else:
        error = ""

    return render_template("host_dev.html", error=error)