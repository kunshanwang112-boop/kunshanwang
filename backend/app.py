# -*- coding: utf-8 -*-
"""
打分小系统 · 后端（公网部署版）
- 打分提交 / 结果计算（去最高最低取平均+排序）/ 导出 CSV / 二维码
- 支持 CORS（供 GitHub Pages 等静态前端跨域调用）
- 数据目录可用环境变量 DATA_DIR 指定（用于免费云后端挂载持久化卷）
- 结果与导出接口需要管理口令（?pwd=），防止公网裸奔

本地运行:
    .venv/bin/python app.py      # 监听 8000
公网部署：见 部署指南.md
"""
import io
import os
import csv
import json
import datetime

from flask import (Flask, request, render_template, jsonify,
                   send_file, redirect, url_for)

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
DATA_PATH = os.path.join(DATA_DIR, "data.json")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "telep-scoring-secret-change-me")


# ---------------- CORS ----------------
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/", methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_ok(path=None):
    return "", 200


# ---------------- 数据 ----------------
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data():
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)


def _safe_name(s):
    return str(s or "").strip()[:40]


def time_now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dims(cfg):
    return cfg.get("dims", [
        {"name": "立足实际场景", "max": 20},
        {"name": "体现赋能价值", "max": 20},
        {"name": "成效真实可验证", "max": 20},
        {"name": "坚持原创合规", "max": 10},
        {"name": "具备推广价值", "max": 30},
    ])


def _admin_ok():
    cfg = load_config()
    return request.args.get("pwd") == cfg.get("admin_pass", "admin123")


# ---------------- 页面（后端自带，也可不用） ----------------
@app.route("/")
def index():
    cfg = load_config()
    return render_template("index.html", rounds=cfg.get("rounds", {}),
                           round_keys=list(cfg.get("rounds", {}).keys()))


@app.route("/score/<round_key>")
def score_page(round_key):
    cfg = load_config()
    if round_key not in cfg.get("rounds", {}):
        return "该轮次不存在", 404
    return render_template("round.html", round_key=round_key,
                           round_name=cfg["rounds"][round_key].get("name", round_key),
                           cases=cfg["rounds"][round_key].get("cases", []),
                           dims=dims(cfg),
                           need_pass=bool(cfg.get("judge_pass", "")))


# ---------------- 提交 ----------------
@app.route("/api/submit", methods=["POST"])
def submit():
    cfg = load_config()
    body = request.get_json(force=True)
    round_key = body.get("round")
    if round_key not in cfg.get("rounds", {}):
        return jsonify(ok=False, msg="轮次无效"), 400

    judge = _safe_name(body.get("judge"))
    if not judge:
        return jsonify(ok=False, msg="请填写评委姓名"), 400
    if cfg.get("judge_pass") and body.get("pass") != cfg.get("judge_pass"):
        return jsonify(ok=False, msg="评分口令不正确"), 403

    cases = cfg["rounds"][round_key].get("cases", [])
    scores = body.get("scores", [])
    if not isinstance(scores, list) or not scores:
        return jsonify(ok=False, msg="没有可提交的打分"), 400

    cleaned = []
    for item in scores:
        idx = item.get("case")
        if not (isinstance(idx, int) and 0 <= idx < len(cases)):
            continue
        total = item.get("total")
        if total is None or total == "":
            continue
        try:
            total = round(float(total))
        except (TypeError, ValueError):
            return jsonify(ok=False, msg="总分必须是数字"), 400
        if total < 0 or total > 100:
            return jsonify(ok=False, msg="总分须在 0—100 之间"), 400

        raw_dims = item.get("dims", {}) or {}
        dim_vals = []
        for d in dims(cfg):
            v = raw_dims.get(d["name"])
            if v is None or v == "":
                dim_vals.append(None)
            else:
                try:
                    dim_vals.append(round(float(v)))
                except (TypeError, ValueError):
                    dim_vals.append(None)
        cleaned.append({"case": idx, "total": total, "dims": dim_vals})

    if not cleaned:
        return jsonify(ok=False, msg="至少填写一个案例的总分"), 400

    data = load_data()
    subs = data.setdefault(round_key, {}).setdefault("submissions", [])
    subs = [s for s in subs if s.get("judge") != judge]
    subs.append({"judge": judge, "ts": time_now(), "scores": cleaned})
    data[round_key]["submissions"] = subs
    save_data(data)
    return jsonify(ok=True, msg="已提交评委「%s」的打分（同名重复提交将覆盖）" % judge)


# ---------------- 结果 ----------------
def compute_round(round_key, cfg, data):
    cases = cfg["rounds"][round_key].get("cases", [])
    subs = data.get(round_key, {}).get("submissions", [])
    results = []
    for idx, cname in enumerate(cases):
        totals = []
        for s in subs:
            for sc in s.get("scores", []):
                if sc.get("case") == idx:
                    totals.append(sc.get("total"))
        if not totals:
            continue
        if len(totals) >= 3:
            t = sorted(totals)
            avg = round(sum(t[1:-1]) / (len(t) - 2), 2)
        else:
            avg = round(sum(totals) / len(totals), 2)
        results.append({"case": cname, "count": len(totals),
                        "max": max(totals), "min": min(totals), "score": avg})
    results.sort(key=lambda x: x["score"], reverse=True)
    rank, prev = 0, None
    for it in results:
        if prev is None or it["score"] != prev:
            rank += 1
            prev = it["score"]
        it["rank"] = rank
    return {"round_name": cfg["rounds"][round_key].get("name", round_key),
            "judge_count": len(subs), "case_count": len(cases),
            "results": results}


@app.route("/api/results")
def api_results():
    if not _admin_ok():
        return jsonify(ok=False, msg="口令错误"), 401
    cfg = load_config()
    data = load_data()
    out = {}
    for rk in cfg.get("rounds", {}):
        out[rk] = compute_round(rk, cfg, data)
    return jsonify(out)


@app.route("/api/export/<round_key>.csv")
def api_export(round_key):
    if not _admin_ok():
        return "口令错误", 401
    cfg = load_config()
    if round_key not in cfg.get("rounds", {}):
        return "轮次不存在", 404
    res = compute_round(round_key, cfg, load_data())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["排名", "案例名称", "有效专家数", "最高分", "最低分", "去极值平均分"])
    for it in res["results"]:
        w.writerow([it["rank"], it["case"], it["count"], it["max"], it["min"], it["score"]])
    fname = "%s_%s.csv" % (round_key, datetime.datetime.now().strftime("%Y%m%d"))
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8-sig")),
                     mimetype="text/csv", as_attachment=True, download_name=fname)


# ---------------- 二维码 ----------------
@app.route("/qr/<round_key>")
def qr(round_key):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    cfg = load_config()
    rk_cfg = cfg.get("rounds", {}).get(round_key, {})
    url = rk_cfg.get("public_url") or \
        ("%s/score/%s" % (cfg.get("public_base_url", request.url_root.rstrip("/")), round_key))
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)