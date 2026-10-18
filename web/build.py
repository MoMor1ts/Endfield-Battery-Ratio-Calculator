# -*- coding: utf-8 -*-
"""
把 template.html + ../resource 里的图片打包成单文件 index.html（图片内嵌 base64）。
只需要标准库，不需要 Pillow。

用法：  python build.py
"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
RES = os.path.join(PROJECT, "resource")
TEMPLATE = os.path.join(HERE, "template.html")
OUT = os.path.join(HERE, "index.html")

FILES = ["gudi_low.png", "gudi_mid.png", "gudi_high.png",
         "wuling_low.png", "wuling_mid.png", "logo.png",
         "build_pickup.png", "build_deposit.png", "build_thermal.png", "build_thermal_big.png",
         "build_bridge.png",
         "build_belt_0.png", "build_belt_1.png", "build_belt_2.png", "build_belt_3.png",
         "build_corner_0.png", "build_corner_1.png", "build_corner_2.png", "build_corner_3.png",
         "build_corner_m0.png", "build_corner_m1.png", "build_corner_m2.png", "build_corner_m3.png",
         "build_splitter_0.png", "build_splitter_1.png", "build_splitter_2.png", "build_splitter_3.png",
         "build_merger_0.png", "build_merger_1.png", "build_merger_2.png", "build_merger_3.png",
         "build_gate_gudi_low.png", "build_gate_gudi_mid.png", "build_gate_gudi_high.png",
         "build_gate_wuling_low.png", "build_gate_wuling_mid.png",
         "build_splitter.png", "build_merger.png", "build_belt.png", "build_corner.png"]


def data_uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def main():
    images = {}
    for name in FILES:
        path = os.path.join(RES, name)
        if not os.path.isfile(path):
            raise SystemExit("缺少图片: %s" % path)
        images[name] = data_uri(path)
        print("  %-16s %5d KB" % (name, len(images[name]) // 1024))

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("@@IMAGES@@", ",\n".join(
        '  "%s": "%s"' % (k, v) for k, v in images.items()))
    html = html.replace("@@IMG:logo.png@@", images["logo.png"])

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("\n已生成 %s  (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
