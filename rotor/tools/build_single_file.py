#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_single_file.py — funde el proyecto en un único index.html autocontenido,
pensado para GitHub Pages (hosting 100% estático, sin PHP, sin ejecución de
servidor).

Qué hace:
  1. Inserta styles.css dentro de un <style> en el <head>.
  2. Inserta GSAP + ScrollTrigger, el manifiesto de datos y main.js dentro de
     <script> al final del <body> — sin módulos, en el mismo orden en que se
     cargaban como archivos sueltos.
  3. Reescribe el envío del formulario: sin PHP no hay a quién hacer fetch, así
     que el envío pasa a construir un enlace mailto: y abrirlo directamente.
     Es el único camino que funciona en un sitio 100% estático sin backend.
  4. Sustituye el dominio de marcador de posición por uno que se lee
     inequívocamente como "rellena esto", para que no quede sin cambiar por
     descuido.
  5. Incrusta el favicon como data URI (un archivo menos, un 404 menos).
  6. Borra los archivos que quedan redundantes una vez fundidos.

Uso:
    python tools/build_single_file.py
"""

import base64
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PLACEHOLDER_BASE = "https://TU-USUARIO.github.io/TU-REPOSITORIO"


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return f.read()


def read_bin(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return f.read()


def must_replace(s, old, new, label):
    if old not in s:
        sys.exit("ERROR: no se encontró el fragmento esperado (%s)" % label)
    return s.replace(old, new, 1)


def main():
    html = read("index.html")
    css = read("styles.css")
    gsap_js = read("lib/gsap.min.js").strip()
    st_js = read("lib/ScrollTrigger.min.js").strip()
    manifest_js = read("lib/manifest.js")
    main_js = read("main.js")
    favicon_svg = read_bin("assets/img/favicon.svg")

    # -------------------------------------------------------------------
    # 1. Dominio de marcador de posición: uno que grita "cámbiame", no uno
    #    que parezca un dominio real ya configurado.
    # -------------------------------------------------------------------
    html = html.replace("https://rotor.es/", PLACEHOLDER_BASE + "/")

    # -------------------------------------------------------------------
    # 2. Favicon como data URI — un archivo y una petición menos.
    # -------------------------------------------------------------------
    favicon_b64 = base64.b64encode(favicon_svg).decode("ascii")
    favicon_uri = "data:image/svg+xml;base64," + favicon_b64
    html = must_replace(
        html,
        '<link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">\n'
        '<link rel="apple-touch-icon" href="assets/img/favicon.svg">',
        '<link rel="icon" href="%s" type="image/svg+xml">\n'
        "<!-- El favicon va incrustado (data URI): un archivo menos que pueda dar 404.\n"
        "     Para el icono de pantalla de inicio de iOS, Apple solo admite PNG; si\n"
        "     quieres uno específico, añade tu propio "
        '<link rel="apple-touch-icon" href="ruta/a/icono-180.png"> más adelante. -->'
        % favicon_uri,
        "favicon",
    )

    # -------------------------------------------------------------------
    # 3. CSS inline.
    # -------------------------------------------------------------------
    html = must_replace(
        html,
        '<link rel="stylesheet" href="styles.css?v=20260907">',
        "<style>\n" + css + "\n</style>",
        "styles.css link",
    )

    # -------------------------------------------------------------------
    # 4. Formulario: sin PHP, el único camino que funciona en GitHub Pages
    #    es mailto:. El <form> lleva un fallback nativo por si el JS falla;
    #    el main.js de abajo intercepta el submit y hace la versión buena.
    # -------------------------------------------------------------------
    html = must_replace(
        html,
        '<form class="form" data-form action="contacto.php" method="post" novalidate>',
        '<form class="form" data-form action="mailto:hola@rotor.es" '
        'method="post" enctype="text/plain" novalidate>',
        "form action",
    )
    html = must_replace(
        html,
        "<p class=\"form__legal\">Al enviar aceptas que usemos tus datos para responderte. Nada más.</p>",
        "<p class=\"form__legal\">Este sitio no tiene servidor: al enviar se abre tu programa de correo con "
        "el mensaje ya escrito. Nada se guarda ni pasa por terceros.</p>",
        "form legal copy",
    )
    html = must_replace(
        html,
        '<li><svg class="ico" aria-hidden="true"><use href="#i-check"/></svg>Tus datos solo se usan para responderte</li>',
        '<li><svg class="ico" aria-hidden="true"><use href="#i-check"/></svg>No pasa por ningún servidor: se envía desde tu propio correo</li>',
        "aside bullet copy",
    )

    # -------------------------------------------------------------------
    # 5. Los cuatro <script src> sueltos, sustituidos por su contenido.
    # -------------------------------------------------------------------
    manifest_js = manifest_js.replace(
        "      ⚠️ El formulario envía a la dirección configurada en `contacto.php`.\n"
        "         Este correo se usa para el enlace de respaldo si el envío falla.\n",
        "      El formulario abre un mailto: con este correo — no hay servidor detrás.\n",
    )
    manifest_js = must_replace(
        manifest_js,
        "    contacto: {\n"
        '      email: "hola@rotor.es",\n'
        "      // Deja `telefono` como cadena vacía si no quieres mostrarlo.\n"
        '      telefono: "",\n'
        '      endpoint: "contacto.php",\n'
        "    },",
        "    contacto: {\n"
        '      email: "hola@rotor.es", // ⚠️ Debe coincidir con el `action` del <form>.\n'
        "      // Deja `telefono` como cadena vacía si no quieres mostrarlo.\n"
        '      telefono: "",\n'
        "    },",
        "manifest contacto block",
    )
    manifest_js = manifest_js.replace(
        'dominio: "https://rotor.es", // ⚠️ Sustituir por el dominio real.',
        'dominio: "%s/", // ⚠️ Sustituir por tu URL real de GitHub Pages.' % PLACEHOLDER_BASE,
    )

    old_init_form = read("main.js")
    old_init_form = None  # (evita confusión con la variable de arriba)

    main_js = must_replace(
        main_js,
        '''  /* =========================================================================
     Formulario
     -------------------------------------------------------------------------
     Envía de verdad, a `contacto.php`. Si el servidor no responde (por ejemplo
     al abrir la web desde el disco), no se finge un envío correcto: se avisa y
     se ofrece el correo con el mensaje ya escrito.
     ====================================================================== */
  function initForm() {
    var form = $("[data-form]");
    if (!form) return;
    var ok = $("[data-form-ok]");
    var status = $("[data-form-status]");
    var okTitle = $("[data-form-ok-title]");
    var okText = $("[data-form-ok-text]");
    var contacto = data.contacto || {};

    var REGLAS = {
      nombre: { req: true, min: 2, msg: "Escribe tu nombre." },
      email: { req: true, re: /^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/, msg: "Revisa el correo: falta algo." },
      sector: { req: true, msg: "Elige el tipo de negocio." },
      mensaje: { req: true, min: 12, msg: "Cuéntanos un poco más, con una frase basta." }
    };

    function fieldOf(name) {
      var el = form.elements[name];
      return el ? el.closest(".field") : null;
    }

    function validate(name) {
      var rule = REGLAS[name];
      var el = form.elements[name];
      if (!rule || !el) return true;
      var v = (el.value || "").trim();
      var bad = (rule.req && !v) || (rule.min && v.length < rule.min) || (rule.re && !rule.re.test(v));
      var wrap = fieldOf(name);
      if (wrap) {
        wrap.classList.toggle("is-bad", !!bad);
        var err = wrap.querySelector("[data-err-for]");
        if (err) err.textContent = bad ? rule.msg : "";
      }
      return !bad;
    }

    Object.keys(REGLAS).forEach(function (name) {
      var el = form.elements[name];
      if (!el) return;
      el.addEventListener("blur", function () { if (el.value.trim()) validate(name); });
      el.addEventListener("input", function () {
        var wrap = fieldOf(name);
        if (wrap && wrap.classList.contains("is-bad")) validate(name);
      });
      el.addEventListener("change", function () { validate(name); });
    });

    function mailtoFallback(fd) {
      var cuerpo = [
        "Nombre: " + (fd.get("nombre") || ""),
        "Empresa: " + (fd.get("empresa") || ""),
        "Email: " + (fd.get("email") || ""),
        "Tipo de negocio: " + (fd.get("sector") || ""),
        "Objetivo: " + (fd.get("objetivo") || ""),
        "Funcionalidades: " + fd.getAll("funcionalidades[]").join(", "),
        "Presupuesto: " + (fd.get("presupuesto") || "—"),
        "",
        fd.get("mensaje") || ""
      ].join("\\n");
      return "mailto:" + (contacto.email || "") +
        "?subject=" + encodeURIComponent("Quiero crear mi app") +
        "&body=" + encodeURIComponent(cuerpo);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (form.classList.contains("is-sending")) return;
      if (status) status.innerHTML = "";

      var valido = true, primero = null;
      Object.keys(REGLAS).forEach(function (name) {
        var okField = validate(name);
        if (!okField && !primero) primero = form.elements[name];
        valido = valido && okField;
      });
      if (!valido) {
        if (primero) primero.focus();
        return;
      }

      var fd = new FormData(form);

      // Trampa de robots: silencio y a otra cosa.
      if ((fd.get("web") || "").trim()) { form.reset(); return; }

      form.classList.add("is-sending");

      fetch(contacto.endpoint || "contacto.php", {
        method: "POST",
        body: fd,
        headers: { "X-Requested-With": "fetch" }
      })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json().catch(function () { return { ok: true }; });
        })
        .then(function (json) {
          if (json && json.ok === false) throw new Error(json.error || "rechazado");
          var nombre = String(fd.get("nombre") || "").trim().split(/\\s+/)[0];
          if (okTitle) okTitle.textContent = nombre ? "Gracias, " + nombre + "." : "Recibido.";
          if (okText) {
            okText.textContent =
              "Hemos recibido tu mensaje. Lo leemos entero y te respondemos con una primera valoración de lo que nos cuentas.";
          }
          form.hidden = true;
          if (ok) { ok.hidden = false; ok.querySelector("h3").focus && ok.querySelector("h3").focus(); }
        })
        .catch(function (err) {
          console.warn("[form]", err);
          if (status) {
            status.innerHTML =
              "No hemos podido enviar el formulario desde aquí. " +
              'Escríbenos a <a href="' + escHTML(mailtoFallback(fd)) + '">' + escHTML(contacto.email || "") +
              "</a> y te contestamos igual.";
          }
        })
        .then(function () { form.classList.remove("is-sending"); });
    });

    var reset = $("[data-form-reset]");
    if (reset) {
      reset.addEventListener("click", function () {
        form.reset();
        $$(".field.is-bad", form).forEach(function (f) { f.classList.remove("is-bad"); });
        form.hidden = false;
        if (ok) ok.hidden = true;
        var first = form.elements.nombre;
        if (first) first.focus();
      });
    }
  }''',
        '''  /* =========================================================================
     Formulario
     -------------------------------------------------------------------------
     Este sitio es 100% estático (GitHub Pages no ejecuta PHP ni ningún otro
     backend), así que no hay a quién hacer fetch. El único envío que funciona
     de verdad sin servidor es abrir el programa de correo del propio usuario
     con el mensaje ya escrito — por eso el <form> también lleva
     `action="mailto:..."` como red de seguridad si este script no llegara a
     cargar.
     ====================================================================== */
  function initForm() {
    var form = $("[data-form]");
    if (!form) return;
    var ok = $("[data-form-ok]");
    var status = $("[data-form-status]");
    var okTitle = $("[data-form-ok-title]");
    var okText = $("[data-form-ok-text]");
    var contacto = data.contacto || {};

    var REGLAS = {
      nombre: { req: true, min: 2, msg: "Escribe tu nombre." },
      email: { req: true, re: /^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/, msg: "Revisa el correo: falta algo." },
      sector: { req: true, msg: "Elige el tipo de negocio." },
      mensaje: { req: true, min: 12, msg: "Cuéntanos un poco más, con una frase basta." }
    };

    function fieldOf(name) {
      var el = form.elements[name];
      return el ? el.closest(".field") : null;
    }

    function validate(name) {
      var rule = REGLAS[name];
      var el = form.elements[name];
      if (!rule || !el) return true;
      var v = (el.value || "").trim();
      var bad = (rule.req && !v) || (rule.min && v.length < rule.min) || (rule.re && !rule.re.test(v));
      var wrap = fieldOf(name);
      if (wrap) {
        wrap.classList.toggle("is-bad", !!bad);
        var err = wrap.querySelector("[data-err-for]");
        if (err) err.textContent = bad ? rule.msg : "";
      }
      return !bad;
    }

    Object.keys(REGLAS).forEach(function (name) {
      var el = form.elements[name];
      if (!el) return;
      el.addEventListener("blur", function () { if (el.value.trim()) validate(name); });
      el.addEventListener("input", function () {
        var wrap = fieldOf(name);
        if (wrap && wrap.classList.contains("is-bad")) validate(name);
      });
      el.addEventListener("change", function () { validate(name); });
    });

    function buildMailto(fd) {
      var cuerpo = [
        "Nombre: " + (fd.get("nombre") || ""),
        "Empresa: " + (fd.get("empresa") || ""),
        "Email: " + (fd.get("email") || ""),
        "Tipo de negocio: " + (fd.get("sector") || ""),
        "Objetivo: " + (fd.get("objetivo") || ""),
        "Funcionalidades: " + fd.getAll("funcionalidades[]").join(", "),
        "Presupuesto: " + (fd.get("presupuesto") || "—"),
        "",
        fd.get("mensaje") || ""
      ].join("\\n");
      var nombre = String(fd.get("nombre") || "").trim();
      return "mailto:" + (contacto.email || "") +
        "?subject=" + encodeURIComponent("Quiero crear mi app" + (nombre ? " — " + nombre : "")) +
        "&body=" + encodeURIComponent(cuerpo);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (form.classList.contains("is-sending")) return;

      var valido = true, primero = null;
      Object.keys(REGLAS).forEach(function (name) {
        var okField = validate(name);
        if (!okField && !primero) primero = form.elements[name];
        valido = valido && okField;
      });
      if (!valido) {
        if (primero) primero.focus();
        return;
      }

      var fd = new FormData(form);

      // Trampa de robots: silencio y a otra cosa.
      if ((fd.get("web") || "").trim()) { form.reset(); return; }

      var mailto = buildMailto(fd);
      form.classList.add("is-sending");

      // El retardo es deliberado: da tiempo a que el botón muestre el
      // estado de "enviando" un instante antes de que el navegador abra el
      // correo, en vez de que el cambio sea tan instantáneo que no se note.
      setTimeout(function () {
        window.location.href = mailto;

        var nombre = String(fd.get("nombre") || "").trim().split(/\\s+/)[0];
        if (okTitle) okTitle.textContent = nombre ? "Gracias, " + nombre + "." : "Casi listo.";
        if (okText) {
          okText.textContent =
            "Hemos abierto tu programa de correo con el mensaje ya escrito. Solo tienes que darle a enviar.";
        }
        if (status) {
          status.innerHTML =
            "¿No se abrió nada? Escríbenos directamente a " +
            '<a href="' + escHTML(mailto) + '">' + escHTML(contacto.email || "") + "</a>.";
        }
        form.classList.remove("is-sending");
        form.hidden = true;
        if (ok) {
          ok.hidden = false;
          var h3 = ok.querySelector("h3");
          if (h3 && h3.focus) h3.focus();
        }
      }, 380);
    });

    var reset = $("[data-form-reset]");
    if (reset) {
      reset.addEventListener("click", function () {
        form.reset();
        $$(".field.is-bad", form).forEach(function (f) { f.classList.remove("is-bad"); });
        if (status) status.innerHTML = "";
        form.hidden = false;
        if (ok) ok.hidden = true;
        var first = form.elements.nombre;
        if (first) first.focus();
      });
    }
  }''',
        "initForm",
    )
    main_js = main_js.replace(
        "  Script clásico, sin módulos: funciona igual abierto desde el disco que\n"
        "  servido por Apache. Cada init va envuelto en safe(): si uno falla, el resto\n"
        "  sigue vivo.",
        "  Script clásico, sin módulos: funciona igual abierto desde el disco que\n"
        "  servido por GitHub Pages. Cada init va envuelto en safe(): si uno falla,\n"
        "  el resto sigue vivo.",
    )

    html = must_replace(
        html,
        '<script defer src="lib/gsap.min.js"></script>\n'
        '<script defer src="lib/ScrollTrigger.min.js"></script>\n'
        '<script defer src="lib/manifest.js?v=20260907"></script>\n'
        '<script defer src="main.js?v=20260907"></script>',
        "<!-- GSAP + ScrollTrigger (locales, sin CDN: cero peticiones externas de JS) -->\n"
        "<script>\n" + gsap_js + "\n</script>\n"
        "<script>\n" + st_js + "\n</script>\n"
        "<!-- Datos de marca -->\n"
        "<script>\n" + manifest_js.strip() + "\n</script>\n"
        "<!-- Comportamiento -->\n"
        "<script>\n" + main_js.strip() + "\n</script>",
        "script tags",
    )

    out_path = os.path.join(ROOT, "index.html")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    size = os.path.getsize(out_path)
    print("index.html fundido: %d bytes (%.1f KB)" % (size, size / 1024))

    # -------------------------------------------------------------------
    # 6. Limpieza: fuera lo que ha quedado redundante.
    # -------------------------------------------------------------------
    removed = []
    for rel in [
        "styles.css",
        "main.js",
        "contacto.php",
        ".htaccess",
        "lib",
        "assets/img/favicon.svg",
        "assets/img/poster-despiece.webp",  # generado pero nunca referenciado
    ]:
        p = os.path.join(ROOT, rel)
        if os.path.isdir(p):
            shutil.rmtree(p)
            removed.append(rel + "/")
        elif os.path.isfile(p):
            os.remove(p)
            removed.append(rel)
    print("Eliminados (fundidos en index.html o sin uso): " + ", ".join(removed))

    # -------------------------------------------------------------------
    # 7. .nojekyll — evita que GitHub Pages intente procesar el sitio con
    #    Jekyll (no lo necesita; es HTML/CSS/JS ya construido) y con 200
    #    fotogramas sueltos en assets/frames/ es una precaución barata.
    # -------------------------------------------------------------------
    with open(os.path.join(ROOT, ".nojekyll"), "w", encoding="utf-8") as f:
        pass
    print("Creado .nojekyll")

    # -------------------------------------------------------------------
    # 8. robots.txt / sitemap.xml — mismo marcador de posición de dominio.
    # -------------------------------------------------------------------
    for rel in ["robots.txt", "sitemap.xml"]:
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            s = read(rel)
            s = s.replace("https://rotor.es", PLACEHOLDER_BASE)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(s)
    print("Actualizados robots.txt y sitemap.xml")


if __name__ == "__main__":
    main()
