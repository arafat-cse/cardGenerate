// BizCard Studio - Adobe Illustrator automation
//
// Python writes:   illustrator/scripts/current_job.txt  (path of the job folder)
//                  illustrator/jobs/<job>/config.jsx    (var JOB = {...})
// This script:     reads the job, builds a 2-artboard document (front + back),
//                  saves card.ai into the job folder and writes done.json.
//
// Coordinates in JOB items are points, origin = trim top-left, y downward.

(function () {
    var jobDir = "";

    function esc(s) {
        return String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r?\n/g, " ");
    }

    function writeDone(ok, err) {
        try {
            var f = new File(jobDir + "/done.json");
            f.encoding = "UTF-8";
            f.open("w");
            f.write('{"ok":' + (ok ? "true" : "false") + ',"error":"' + esc(err || "") + '"}');
            f.close();
        } catch (e2) {}
    }

    function col(hex) {
        var c = new RGBColor();
        c.red = parseInt(hex.substr(1, 2), 16);
        c.green = parseInt(hex.substr(3, 2), 16);
        c.blue = parseInt(hex.substr(5, 2), 16);
        return c;
    }

    function setFont(ca, names, family, style) {
        var i;
        for (i = 0; i < names.length; i++) {
            try { ca.textFont = app.textFonts.getByName(names[i]); return; } catch (e) {}
        }
        try {
            for (i = 0; i < app.textFonts.length; i++) {
                var tf = app.textFonts[i];
                if (family && tf.family && String(tf.family).toLowerCase() === String(family).toLowerCase()) {
                    if (!style || !tf.style || String(tf.style).toLowerCase() === String(style).toLowerCase()) {
                        ca.textFont = tf;
                        return;
                    }
                }
            }
        } catch (e2) {}
    }

    function style(p, fill, stroke, strokeW) {
        p.filled = !!fill;
        if (fill) p.fillColor = col(fill);
        p.stroked = !!stroke;
        if (stroke) {
            p.strokeColor = col(stroke);
            p.strokeWidth = strokeW || 1;
        }
    }

    function roundedRect(doc, x, y, w, h, r) {
        r = Math.min(r, w / 2, h / 2);
        var k = 0.5523 * r;
        var yb = y - h;
        var p = doc.pathItems.add();
        p.stroked = false;
        p.filled = true;
        function pt(a, l, rr) {
            var q = p.pathPoints.add();
            q.anchor = a;
            q.leftDirection = l;
            q.rightDirection = rr;
            q.pointType = PointType.SMOOTH;
        }
        pt([x + r, y], [x + r - k, y], [x + r + k, y]);
        pt([x + w - r, y], [x + w - r - k, y], [x + w - r + k, y]);
        pt([x + w, y - r], [x + w, y - r - k], [x + w, y - r + k]);
        pt([x + w, yb + r], [x + w, yb + r + k], [x + w, yb + r - k]);
        pt([x + w - r, yb], [x + w - r + k, yb], [x + w - r - k, yb]);
        pt([x + r, yb], [x + r + k, yb], [x + r - k, yb]);
        pt([x, yb + r], [x, yb + r + k], [x, yb + r - k]);
        pt([x, y - r], [x, y - r + k], [x, y - r - k]);
        p.closed = true;
        return p;
    }

    function drawRect(doc, L, T, it, dy) {
        var x = L + it.x, y = T - (it.y + dy), p = null;
        if (it.radius && it.radius > 0.1) {
            try { p = roundedRect(doc, x, y, it.w, it.h, it.radius); } catch (e) { p = null; }
        }
        if (!p) p = doc.pathItems.rectangle(y, x, it.w, it.h);
        style(p, it.fill, it.stroke, it.strokeW);
    }

    function drawEllipse(doc, L, T, it, dy) {
        var x = it.x, y = it.y, w = it.w, h = it.h;
        if (it.circle) {
            var d = Math.min(w, h);
            x += (w - d) / 2;
            y += (h - d) / 2;
            w = d;
            h = d;
        }
        var p = doc.pathItems.ellipse(T - (y + dy), L + x, w, h);
        style(p, it.fill, it.stroke, it.strokeW);
    }

    function drawPoly(doc, L, T, it, dy) {
        var pts = [], i;
        for (i = 0; i < it.pts.length; i++) {
            pts.push([L + it.pts[i][0], T - (it.pts[i][1] + dy)]);
        }
        var p = doc.pathItems.add();
        p.setEntirePath(pts);
        p.closed = true;
        style(p, it.fill, it.stroke, it.strokeW);
    }

    function drawLine(doc, L, T, it, dy) {
        var p = doc.pathItems.add();
        p.setEntirePath([[L + it.x1, T - (it.y1 + dy)], [L + it.x2, T - (it.y2 + dy)]]);
        p.filled = false;
        p.stroked = true;
        p.strokeColor = col(it.stroke);
        p.strokeWidth = it.w || 1;
    }

    function drawImage(doc, L, T, it, dy) {
        var f = new File(jobDir + "/assets/" + it.src);
        if (!f.exists) return;
        var pl = doc.placedItems.add();
        pl.file = f;
        var s = (it.fit === "cover")
            ? Math.max(it.w / pl.width, it.h / pl.height)
            : Math.min(it.w / pl.width, it.h / pl.height);
        pl.width = pl.width * s;
        pl.height = pl.height * s;
        var cx = it.x + (it.w - pl.width) / 2;
        var cy = it.y + (it.h - pl.height) / 2;
        pl.left = L + cx;
        pl.top = T - (cy + dy);
        if (it.circle) {
            var g = doc.groupItems.add();
            pl.move(g, ElementPlacement.PLACEATEND);
            var d = Math.min(it.w, it.h);
            var ex = it.x + (it.w - d) / 2;
            var ey = it.y + (it.h - d) / 2;
            var ring = doc.pathItems.ellipse(T - (ey + dy), L + ex, d, d);
            ring.filled = false;
            ring.stroked = false;
            ring.move(g, ElementPlacement.PLACEATBEGINNING);
            g.clipped = true;
        }
    }

    function drawText(doc, L, T, it, dy) {
        var tf = doc.textFrames.add();
        tf.contents = it.s;
        var ax = it.x;
        if (it.align === "center") ax = it.x + it.w / 2;
        else if (it.align === "right") ax = it.x + it.w;
        tf.top = T - (it.yTop + dy);
        tf.left = L + ax;
        var ca = tf.textRange.characterAttributes;
        ca.size = it.size;
        if (it.track) ca.tracking = Math.round(it.track * 1000);
        ca.fillColor = col(it.color);
        setFont(ca, it.font || [], it.family, it.style);
        var pa = tf.textRange.paragraphAttributes;
        pa.justification = (it.align === "center") ? Justification.CENTER
            : ((it.align === "right") ? Justification.RIGHT : Justification.LEFT);
    }

    try {
        var sf = new File(new File($.fileName).parent + "/current_job.txt");
        if (!sf.exists) throw new Error("current_job.txt not found next to the script");
        sf.open("r");
        jobDir = sf.read();
        sf.close();
        jobDir = jobDir.replace(/^\s+|\s+$/g, "");

        $.evalFile(jobDir + "/config.jsx");

        var b = JOB.doc.bleed;
        var doc = app.documents.add(
            DocumentColorSpace.RGB,
            JOB.doc.w + 2 * b,
            2 * JOB.doc.h + JOB.doc.gap + 2 * b
        );
        var ab = doc.artboards[0].artboardRect; // [left, top, right, bottom]
        var L = ab[0], T = ab[1];
        doc.artboards[0].artboardRect = [L - b, T + b, L + JOB.doc.w + b, T - JOB.doc.h - b];
        var backTop = T - JOB.doc.h - JOB.doc.gap;
        doc.artboards.add([L - b, backTop + b, L + JOB.doc.w + b, backTop - JOB.doc.h - b]);

        for (var i = 0; i < JOB.items.length; i++) {
            var it = JOB.items[i];
            var dy = it.dy || 0;
            if (it.t === "rect") drawRect(doc, L, T, it, dy);
            else if (it.t === "ellipse") drawEllipse(doc, L, T, it, dy);
            else if (it.t === "poly") drawPoly(doc, L, T, it, dy);
            else if (it.t === "line") drawLine(doc, L, T, it, dy);
            else if (it.t === "image") drawImage(doc, L, T, it, dy);
            else if (it.t === "text") drawText(doc, L, T, it, dy);
        }

        doc.saveAs(new File(jobDir + "/" + JOB.out.ai));
        writeDone(true, "");
    } catch (e) {
        writeDone(false, (e && e.message) ? e.message : String(e));
    }
})();
