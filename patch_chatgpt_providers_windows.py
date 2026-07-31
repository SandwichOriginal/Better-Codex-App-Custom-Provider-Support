#!/usr/bin/env python3
"""Install the custom model-provider picker patch into ChatGPT/Codex on Windows.

This is a Windows-native port of the macOS installer. The patch is intentionally
version-sensitive: it only edits JavaScript bundles whose expected source hunks
match exactly. App updates that change those bundles cause a clean failure before
the installed app is modified.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import ctypes
import ctypes.wintypes as wintypes
import fnmatch
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any, NoReturn


PATCH_MARKER = b"__codexDesktopModelProvidersPatchV3"
LEGACY_PATCH_MARKER = b"__codexDesktopModelProvidersPatchV2"
ASAR_PACKAGE = "@electron/asar@3.2.10"
PRETTIER_PACKAGE = "prettier@3.6.2"
WINDOWS_INTEGRITY_TYPE = "Integrity"
WINDOWS_INTEGRITY_NAME = "ElectronAsar"
WINDOWS_RESOURCE_LANG = 1033

DEFAULT_PROVIDER_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_provider": "openai",
    "providers": [
        {
            "id": "openai",
            "label": "ChatGPT / OpenAI",
            "description": (
                "Built-in provider; uses your signed-in ChatGPT account"
            ),
        },
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "description": (
                "Custom provider; uses [model_providers.openrouter] from config.toml"
            ),
        },
    ],
    "model_providers": {
        "moonshotai/kimi-k3": "openrouter",
        "x-ai/grok-4.5": "openrouter",
        "anthropic/claude-fable-5": "openrouter",
    },
}


CENTRAL_DIFF = r"""@@ -4631,6 +4631,146 @@
   if (`data` in e) return e;
   let t = oe(e);
   return t == null ? e : { ...e, data: t };
+}
+function codexProviderRoutingFallback() {
+  return {
+    version: 1,
+    defaultProvider: `openai`,
+    providers: [
+      {
+        id: `openai`,
+        label: `ChatGPT / OpenAI`,
+        description: `Uses your signed-in ChatGPT account`,
+      },
+      {
+        id: `openrouter`,
+        label: `OpenRouter`,
+        description: `Uses the OpenRouter provider from config.toml`,
+      },
+    ],
+    modelProviders: {
+      "moonshotai/kimi-k3": `openrouter`,
+      "x-ai/grok-4.5": `openrouter`,
+      "anthropic/claude-fable-5": `openrouter`,
+    },
+  };
+}
+function codexNormalizeProviderRoutingConfig(e) {
+  if (e == null || typeof e !== `object` || Array.isArray(e))
+    throw Error(`Expected a JSON object`);
+  if (e.version !== 1) throw Error(`Unsupported version`);
+  if (!Array.isArray(e.providers) || e.providers.length === 0)
+    throw Error(`providers must be a non-empty array`);
+  let t = [],
+    n = new Set();
+  for (let r of e.providers) {
+    if (r == null || typeof r !== `object` || Array.isArray(r))
+      throw Error(`Every provider must be an object`);
+    let e = typeof r.id === `string` ? r.id.trim() : ``;
+    if (e.length === 0 || n.has(e))
+      throw Error(`Provider ids must be unique non-empty strings`);
+    n.add(e);
+    let i = typeof r.label === `string` ? r.label.trim() : ``;
+    t.push({
+      id: e,
+      label: i.length > 0 ? i : e,
+      description:
+        typeof r.description === `string` ? r.description.trim() : ``,
+    });
+  }
+  let r =
+    typeof e.default_provider === `string` ? e.default_provider.trim() : ``;
+  if (!n.has(r))
+    throw Error(`default_provider must reference a configured provider`);
+  let i = {};
+  if (
+    e.model_providers == null ||
+    typeof e.model_providers !== `object` ||
+    Array.isArray(e.model_providers)
+  )
+    throw Error(`model_providers must be an object`);
+  for (let [t, r] of Object.entries(e.model_providers)) {
+    let e = t.trim();
+    if (e.length === 0 || typeof r !== `string` || !n.has(r))
+      throw Error(`Every model mapping must reference a configured provider`);
+    i[e] = r;
+  }
+  return {
+    version: 1,
+    defaultProvider: r,
+    providers: t,
+    modelProviders: i,
+  };
+}
+function codexProviderRoutingState() {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
+    config: codexProviderRoutingFallback(),
+    configPath: null,
+    error: null,
+    loaded: !1,
+    promise: null,
+  });
+}
+async function codexLoadProviderRoutingConfig(e = !1) {
+  let t = codexProviderRoutingState();
+  if (!e && t.loaded) return t.config;
+  if (t.promise != null) return t.promise;
+  return (
+    (t.promise = (async () => {
+      try {
+        let { codexHome: e } = await Xe(`codex-home`, {
+            params: { hostId: `local` },
+          }),
+          n = e.includes(`\\`) && !e.includes(`/`) ? `\\` : `/`,
+          r = `${e.replace(/[\\/]+$/u, ``)}${n}desktop-model-providers.json`,
+          { contents: i } = await Xe(`read-file`, {
+            params: { hostId: `local`, path: r },
+          }),
+          a = codexNormalizeProviderRoutingConfig(JSON.parse(i));
+        return (
+          (t.config = a),
+          (t.configPath = r),
+          (t.error = null),
+          (t.loaded = !0),
+          a
+        );
+      } catch (e) {
+        return (
+          (t.config = codexProviderRoutingFallback()),
+          (t.error = e instanceof Error ? e.message : String(e)),
+          (t.loaded = !0),
+          t.config
+        );
+      } finally {
+        t.promise = null;
+      }
+    })()),
+    t.promise
+  );
+}
+function codexCustomProviderChoice(e) {
+  try {
+    let t = window.localStorage.getItem(`codex.customProviderSelection.v1`);
+    return t === `auto` || e.providers.some((e) => e.id === t) ? t : `auto`;
+  } catch {
+    return `auto`;
+  }
+}
+async function codexProviderForThreadStart(e) {
+  let t = await codexLoadProviderRoutingConfig(!0),
+    n = codexCustomProviderChoice(t);
+  return n === `auto` ? (t.modelProviders[e?.model] ?? t.defaultProvider) : n;
+}
+async function codexPatchAppServerParams(e, t) {
+  if (e === `thread/list`) {
+    let e = t != null && typeof t === `object` ? t : {};
+    return e.modelProviders == null ? { ...e, modelProviders: [] } : e;
+  }
+  if (e === `thread/start` && t != null && typeof t === `object`)
+    return t.modelProvider == null
+      ? { ...t, modelProvider: await codexProviderForThreadStart(t) }
+      : t;
+  return t;
 }
 var jf,
   Mf,
@@ -4800,6 +4940,7 @@
             throw Error(
               `AppServerRequestClient is missing a message dispatcher`,
             );
+          t = await codexPatchAppServerParams(e, t);
           return e === `config/read`
             ? this.sendConfigReadRequest(t, n)
             : this.enqueueRequest(e, t, n);
@@ -4809,6 +4950,7 @@
             throw Error(
               `AppServerRequestClient is missing a message dispatcher`,
             );
+          e = await codexPatchAppServerParams(`thread/start`, e);
           return this.enqueueRequest(
             `thread/start`,
             e,
"""


PICKER_DIFF = r"""@@ -10162,6 +10162,204 @@
       };
 }
 var jO = e(() => {});
+function codexPickerProviderRoutingFallback() {
+  return {
+    version: 1,
+    defaultProvider: `openai`,
+    providers: [
+      {
+        id: `openai`,
+        label: `ChatGPT / OpenAI`,
+        description: `Uses your signed-in ChatGPT account`,
+      },
+      {
+        id: `openrouter`,
+        label: `OpenRouter`,
+        description: `Uses the OpenRouter provider from config.toml`,
+      },
+    ],
+    modelProviders: {
+      "moonshotai/kimi-k3": `openrouter`,
+      "x-ai/grok-4.5": `openrouter`,
+      "anthropic/claude-fable-5": `openrouter`,
+    },
+  };
+}
+function codexPickerNormalizeProviderRoutingConfig(e) {
+  if (e == null || typeof e !== `object` || Array.isArray(e))
+    throw Error(`Expected a JSON object`);
+  if (e.version !== 1) throw Error(`Unsupported version`);
+  if (!Array.isArray(e.providers) || e.providers.length === 0)
+    throw Error(`providers must be a non-empty array`);
+  let t = [],
+    n = new Set();
+  for (let r of e.providers) {
+    if (r == null || typeof r !== `object` || Array.isArray(r))
+      throw Error(`Every provider must be an object`);
+    let e = typeof r.id === `string` ? r.id.trim() : ``;
+    if (e.length === 0 || n.has(e))
+      throw Error(`Provider ids must be unique non-empty strings`);
+    n.add(e);
+    let i = typeof r.label === `string` ? r.label.trim() : ``;
+    t.push({
+      id: e,
+      label: i.length > 0 ? i : e,
+      description:
+        typeof r.description === `string` ? r.description.trim() : ``,
+    });
+  }
+  let r =
+    typeof e.default_provider === `string` ? e.default_provider.trim() : ``;
+  if (!n.has(r))
+    throw Error(`default_provider must reference a configured provider`);
+  let i = {};
+  if (
+    e.model_providers == null ||
+    typeof e.model_providers !== `object` ||
+    Array.isArray(e.model_providers)
+  )
+    throw Error(`model_providers must be an object`);
+  for (let [t, r] of Object.entries(e.model_providers)) {
+    let e = t.trim();
+    if (e.length === 0 || typeof r !== `string` || !n.has(r))
+      throw Error(`Every model mapping must reference a configured provider`);
+    i[e] = r;
+  }
+  return {
+    version: 1,
+    defaultProvider: r,
+    providers: t,
+    modelProviders: i,
+  };
+}
+function codexPickerProviderRoutingState() {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
+    config: codexPickerProviderRoutingFallback(),
+    configPath: null,
+    error: null,
+    loaded: !1,
+    promise: null,
+  });
+}
+async function codexPickerLoadProviderRoutingConfig(e = !1) {
+  let t = codexPickerProviderRoutingState();
+  if (!e && t.loaded) return t.config;
+  if (t.promise != null) return t.promise;
+  return (
+    (t.promise = (async () => {
+      try {
+        let { codexHome: e } = await ye(`codex-home`, {
+            params: { hostId: `local` },
+          }),
+          n = e.includes(`\\`) && !e.includes(`/`) ? `\\` : `/`,
+          r = `${e.replace(/[\\/]+$/u, ``)}${n}desktop-model-providers.json`;
+        t.configPath = r;
+        let { contents: i } = await ye(`read-file`, {
+            params: { hostId: `local`, path: r },
+          }),
+          a = codexPickerNormalizeProviderRoutingConfig(JSON.parse(i));
+        return ((t.config = a), (t.error = null), (t.loaded = !0), a);
+      } catch (e) {
+        return (
+          (t.config = codexPickerProviderRoutingFallback()),
+          (t.error = e instanceof Error ? e.message : String(e)),
+          (t.loaded = !0),
+          t.config
+        );
+      } finally {
+        t.promise = null;
+      }
+    })()),
+    t.promise
+  );
+}
+function codexReadCustomProviderChoice(e) {
+  try {
+    let t = window.localStorage.getItem(`codex.customProviderSelection.v1`);
+    return t === `auto` || e.providers.some((e) => e.id === t) ? t : `auto`;
+  } catch {
+    return `auto`;
+  }
+}
+function codexWriteCustomProviderChoice(e) {
+  try {
+    window.localStorage.setItem(`codex.customProviderSelection.v1`, e);
+  } catch {}
+}
+function CodexCustomProviderPickerSection() {
+  let r = codexPickerProviderRoutingState(),
+    [e, t] = CodexProviderPatchReact.useState(r.config),
+    [n, i] = CodexProviderPatchReact.useState(r.error),
+    [a, o] = CodexProviderPatchReact.useState(() =>
+      codexReadCustomProviderChoice(r.config),
+    );
+  CodexProviderPatchReact.useEffect(() => {
+    let e = !0;
+    return (
+      codexPickerLoadProviderRoutingConfig(!0).then((n) => {
+        e &&
+          (t(n),
+          i(codexPickerProviderRoutingState().error),
+          o((e) =>
+            e === `auto` || n.providers.some((t) => t.id === e) ? e : `auto`,
+          ));
+      }),
+      () => {
+        e = !1;
+      }
+    );
+  }, []);
+  let s = (e) => (t) => {
+      (t?.preventDefault(), codexWriteCustomProviderChoice(e), o(e));
+    },
+    c =
+      e.providers.find((t) => t.id === e.defaultProvider)?.label ??
+      e.defaultProvider,
+    l = e.providers.map((e) =>
+      (0, FO.jsx)(
+        zy.Item,
+        {
+          RightIcon: a === e.id ? ct : void 0,
+          SubText:
+            e.description.length === 0
+              ? null
+              : (0, FO.jsx)(`span`, {
+                  className: `text-token-description-foreground`,
+                  children: e.description,
+                }),
+          onSelect: s(e.id),
+          children: e.label,
+        },
+        e.id,
+      ),
+    );
+  return (0, FO.jsxs)(FO.Fragment, {
+    children: [
+      (0, FO.jsx)(zy.Title, { children: `Provider for new tasks` }),
+      n == null
+        ? null
+        : (0, FO.jsx)(zy.Item, {
+            disabled: !0,
+            SubText: (0, FO.jsx)(`span`, {
+              className: `text-token-description-foreground`,
+              children: n,
+            }),
+            children: `Provider config error — using fallback`,
+          }),
+      (0, FO.jsx)(zy.Item, {
+        RightIcon: a === `auto` ? ct : void 0,
+        SubText: (0, FO.jsx)(`span`, {
+          className: `text-token-description-foreground`,
+          children: `Uses the mapped provider for each model; ${c} when unmapped`,
+        }),
+        onSelect: s(`auto`),
+        children: `Automatic`,
+      }),
+      l,
+      (0, FO.jsx)(zy.Separator, {}),
+    ],
+  });
+}
 function MO(e) {
   let t = (0, PO.c)(169),
     {
@@ -10312,6 +10510,7 @@
       ? (s = t[48])
       : ((s = (0, FO.jsxs)(FO.Fragment, {
           children: [
+            (0, FO.jsx)(CodexCustomProviderPickerSection, {}),
             a,
             (0, FO.jsx)(`div`, {
               className: `vertical-scroll-fade-mask flex max-h-[250px] flex-col overflow-y-auto`,
@@ -10984,8 +11183,10 @@
 }
 var PO,
   FO,
+  CodexProviderPatchReact,
   IO = e(() => {
     ((PO = w()),
+      (CodexProviderPatchReact = t(m(), 1)),
       T(),
       Q(),
       Pg(),
"""


# ChatGPT 26.721 moved both targets into app-initial, renamed the minified
# bindings, and introduced the Power Picker. Keep a separate exact-hunk variant
# so unsupported future builds still fail before the installed app is touched.
def derive_versioned_diff(base: str, replacements: tuple[tuple[str, str, int], ...]) -> str:
    """Derive an exact-hunk build variant while verifying every fragile rename.

    Electron's bundler changes short identifiers between releases even when the
    surrounding behavior is unchanged. Expected occurrence counts deliberately
    turn an accidental partial replacement into an installer-development error.
    """
    derived = base
    for old, new, expected_count in replacements:
        actual_count = derived.count(old)
        if actual_count != expected_count:
            message = f"Versioned patch replacement count changed for {old!r}: expected {expected_count}, found {actual_count}"
            raise RuntimeError(message)
        derived = derived.replace(old, new)
    return derived


CENTRAL_RENAMES_26721 = (
    ("   let t = oe(e);", "   let t = abe(e);", 1),
    ("await Xe(`codex-home`", "await tp(`codex-home`", 1),
    ("await Xe(`read-file`", "await tp(`read-file`", 1),
    (" var jf,\n   Mf,", " var s9t,\n   c9t,", 1),
    (
        """@@ -4809,6 +4950,7 @@
             throw Error(
               `AppServerRequestClient is missing a message dispatcher`,
             );
+          e = await codexPatchAppServerParams(`thread/start`, e);
           return this.enqueueRequest(
             `thread/start`,
             e,
""",
        """@@ -137758,6 +137899,7 @@
             throw Error(
               `AppServerRequestClient is missing a message dispatcher`,
             );
+          e = await codexPatchAppServerParams(`thread/start`, e);
           let n = t?.priority ?? `critical`,
             r = Q7t(`thread/start`, t?.source),
             i =
""",
        1,
    ),
)
CENTRAL_DIFF_26721 = derive_versioned_diff(CENTRAL_DIFF, CENTRAL_RENAMES_26721)


PICKER_DIFF_26721 = r"""@@ -520849,7 +520849,7 @@
 }
 function Scs(e) {
-  let t = (0, wcs.c)(12),
+  let t = (0, wcs.c)(13),
     { submenu: n } = e,
     r = n.ariaLabel,
     i = n.contentClassName,
@@ -520871,10 +520871,15 @@
     t[7] !== n.label ||
     t[8] !== n.value ||
     t[9] !== o ||
-    t[10] !== l
+    t[10] !== l ||
+    t[11] !== n.extras
       ? ((u = (0, QX.jsx)(Kos, {
           ariaLabel: r,
           contentClassName: i,
           disabled: a,
           flyoutHeader: o,
           label: s,
           value: c,
-          children: l,
+          children:
+            n.extras == null
+              ? l
+              : (0, QX.jsxs)(QX.Fragment, { children: [n.extras, l] }),
         })),
         (t[4] = n.ariaLabel),
         (t[5] = n.contentClassName),
@@ -520887,8 +520892,9 @@
         (t[8] = n.value),
         (t[9] = o),
         (t[10] = l),
-        (t[11] = u))
-      : (u = t[11]),
+        (t[11] = n.extras),
+        (t[12] = u))
+      : (u = t[12]),
     u
   );
 }
@@ -549520,6 +549525,202 @@
       (xMs = Aa(Q, (e, { get: t }) =>
         bMs({
           conversationId: e,
           resumeState: t(PD, e) ?? void 0,
           turnCount: t(LD, e),
         }),
       )));
   });
+function codexPickerProviderRoutingFallback() {
+  return {
+    version: 1,
+    defaultProvider: `openai`,
+    providers: [
+      {
+        id: `openai`,
+        label: `ChatGPT / OpenAI`,
+        description: `Uses your signed-in ChatGPT account`,
+      },
+      {
+        id: `openrouter`,
+        label: `OpenRouter`,
+        description: `Uses the OpenRouter provider from config.toml`,
+      },
+    ],
+    modelProviders: {
+      "moonshotai/kimi-k3": `openrouter`,
+      "x-ai/grok-4.5": `openrouter`,
+      "anthropic/claude-fable-5": `openrouter`,
+    },
+  };
+}
+function codexPickerNormalizeProviderRoutingConfig(e) {
+  if (e == null || typeof e !== `object` || Array.isArray(e))
+    throw Error(`Expected a JSON object`);
+  if (e.version !== 1) throw Error(`Unsupported version`);
+  if (!Array.isArray(e.providers) || e.providers.length === 0)
+    throw Error(`providers must be a non-empty array`);
+  let t = [],
+    n = new Set();
+  for (let r of e.providers) {
+    if (r == null || typeof r !== `object` || Array.isArray(r))
+      throw Error(`Every provider must be an object`);
+    let e = typeof r.id === `string` ? r.id.trim() : ``;
+    if (e.length === 0 || n.has(e))
+      throw Error(`Provider ids must be unique non-empty strings`);
+    n.add(e);
+    let i = typeof r.label === `string` ? r.label.trim() : ``;
+    t.push({
+      id: e,
+      label: i.length > 0 ? i : e,
+      description:
+        typeof r.description === `string` ? r.description.trim() : ``,
+    });
+  }
+  let r =
+    typeof e.default_provider === `string` ? e.default_provider.trim() : ``;
+  if (!n.has(r))
+    throw Error(`default_provider must reference a configured provider`);
+  let i = {};
+  if (
+    e.model_providers == null ||
+    typeof e.model_providers !== `object` ||
+    Array.isArray(e.model_providers)
+  )
+    throw Error(`model_providers must be an object`);
+  for (let [t, r] of Object.entries(e.model_providers)) {
+    let e = t.trim();
+    if (e.length === 0 || typeof r !== `string` || !n.has(r))
+      throw Error(`Every model mapping must reference a configured provider`);
+    i[e] = r;
+  }
+  return {
+    version: 1,
+    defaultProvider: r,
+    providers: t,
+    modelProviders: i,
+  };
+}
+function codexPickerProviderRoutingState() {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
+    config: codexPickerProviderRoutingFallback(),
+    configPath: null,
+    error: null,
+    loaded: !1,
+    promise: null,
+  });
+}
+async function codexPickerLoadProviderRoutingConfig(e = !1) {
+  let t = codexPickerProviderRoutingState();
+  if (!e && t.loaded) return t.config;
+  if (t.promise != null) return t.promise;
+  return (
+    (t.promise = (async () => {
+      try {
+        let { codexHome: e } = await tp(`codex-home`, {
+            params: { hostId: `local` },
+          }),
+          n = e.includes(`\\`) && !e.includes(`/`) ? `\\` : `/`,
+          r = `${e.replace(/[\\/]+$/u, ``)}${n}desktop-model-providers.json`;
+        t.configPath = r;
+        let { contents: i } = await tp(`read-file`, {
+            params: { hostId: `local`, path: r },
+          }),
+          a = codexPickerNormalizeProviderRoutingConfig(JSON.parse(i));
+        return ((t.config = a), (t.error = null), (t.loaded = !0), a);
+      } catch (e) {
+        return (
+          (t.config = codexPickerProviderRoutingFallback()),
+          (t.error = e instanceof Error ? e.message : String(e)),
+          (t.loaded = !0),
+          t.config
+        );
+      } finally {
+        t.promise = null;
+      }
+    })()),
+    t.promise
+  );
+}
+function codexReadCustomProviderChoice(e) {
+  try {
+    let t = window.localStorage.getItem(`codex.customProviderSelection.v1`);
+    return t === `auto` || e.providers.some((e) => e.id === t) ? t : `auto`;
+  } catch {
+    return `auto`;
+  }
+}
+function codexWriteCustomProviderChoice(e) {
+  try {
+    window.localStorage.setItem(`codex.customProviderSelection.v1`, e);
+  } catch {}
+}
+function CodexCustomProviderPickerSection() {
+  let r = codexPickerProviderRoutingState(),
+    [e, t] = CodexProviderPatchReact.useState(r.config),
+    [n, i] = CodexProviderPatchReact.useState(r.error),
+    [a, o] = CodexProviderPatchReact.useState(() =>
+      codexReadCustomProviderChoice(r.config),
+    );
+  CodexProviderPatchReact.useEffect(() => {
+    let e = !0;
+    return (
+      codexPickerLoadProviderRoutingConfig(!0).then((n) => {
+        e &&
+          (t(n),
+          i(codexPickerProviderRoutingState().error),
+          o((e) =>
+            e === `auto` || n.providers.some((t) => t.id === e) ? e : `auto`,
+          ));
+      }),
+      () => {
+        e = !1;
+      }
+    );
+  }, []);
+  let s = (e) => (t) => {
+      (t?.preventDefault(), codexWriteCustomProviderChoice(e), o(e));
+      void Rf(`clear-prewarmed-threads-for-host`, { hostId: `local` }).catch(
+        () => {},
+      );
+    },
+    c =
+      e.providers.find((t) => t.id === e.defaultProvider)?.label ??
+      e.defaultProvider,
+    l = e.providers.map((e) =>
+      (0, wQ.jsx)(
+        yz.Item,
+        {
+          RightIcon: a === e.id ? Ym : void 0,
+          SubText:
+            e.description.length === 0
+              ? null
+              : (0, wQ.jsx)(`span`, {
+                  className: `text-token-description-foreground`,
+                  children: e.description,
+                }),
+          onSelect: s(e.id),
+          children: e.label,
+        },
+        e.id,
+      ),
+    );
+  return (0, wQ.jsxs)(wQ.Fragment, {
+    children: [
+      (0, wQ.jsx)(yz.Title, { children: `Provider for new tasks` }),
+      n == null
+        ? null
+        : (0, wQ.jsx)(yz.Item, {
+            disabled: !0,
+            SubText: (0, wQ.jsx)(`span`, {
+              className: `text-token-description-foreground`,
+              children: n,
+            }),
+            children: `Provider config error — using fallback`,
+          }),
+      (0, wQ.jsx)(yz.Item, {
+        RightIcon: a === `auto` ? Ym : void 0,
+        SubText: (0, wQ.jsx)(`span`, {
+          className: `text-token-description-foreground`,
+          children: `Uses the mapped provider for each model; ${c} when unmapped`,
+        }),
+        onSelect: s(`auto`),
+        children: `Automatic`,
+      }),
+      l,
+      (0, wQ.jsx)(yz.Separator, {}),
+    ],
+  });
+}
 function CMs(e) {
   let t = (0, TMs.c)(164),
@@ -549693,6 +549895,7 @@
           value: s,
         },
         model: {
+          extras: (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
           ariaLabel: U.formatMessage(
             {
               id: `composer.intelligenceDropdown.model.rowAriaLabel`,
@@ -549782,6 +549985,7 @@
       : ((g = (0, wQ.jsxs)(wQ.Fragment, {
           children: [
+            (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
             m,
             (0, wQ.jsx)(`div`, {
               className: `vertical-scroll-fade-mask flex max-h-[250px] flex-col overflow-y-auto`,
@@ -550438,11 +550642,13 @@
 }
 var TMs,
   wQ,
+  CodexProviderPatchReact,
   EMs = e(() => {
     ((TMs = c()),
+      (CodexProviderPatchReact = r(o(), 1)),
       pd(),
       ad(),
       gls(),
"""


# Build 6067 preserves the 26.721 behavior and menu structure, but the bundler
# renamed the surrounding symbols. Derive this layout from the verified 26.721
# patch so the shared routing and picker implementation cannot drift.
CENTRAL_RENAMES_26727 = (
    ("   let t = abe(e);", "   let t = rSe(e);", 1),
    ("await tp(`codex-home`", "await rp(`codex-home`", 1),
    ("await tp(`read-file`", "await rp(`read-file`", 1),
    (" var s9t,\n   c9t,", " var xdn,\n   Sdn,", 1),
    (
        "            r = Q7t(`thread/start`, t?.source),",
        "            r = fdn(`thread/start`, t?.source),",
        1,
    ),
)
CENTRAL_DIFF_26727 = derive_versioned_diff(CENTRAL_DIFF_26721, CENTRAL_RENAMES_26727)


PICKER_RENAMES_26727 = (
    ("function Scs(e) {", "function Mws(e) {", 1),
    ("wcs.c", "Pws.c", 2),
    ("QX", "JY", 3),
    ("Kos", "nCs", 1),
    ("xMs", "XJs", 1),
    ("Aa", "Ca", 1),
    ("bMs", "YJs", 1),
    ("PD", "aD", 1),
    ("LD", "lD", 1),
    ("await tp(`codex-home`", "await rp(`codex-home`", 1),
    ("await tp(`read-file`", "await rp(`read-file`", 1),
    (
        "void Rf(`clear-prewarmed-threads-for-host`",
        "void rp(`clear-prewarmed-threads-for-host`",
        1,
    ),
    ("wQ", "CZ", 16),
    ("yz", "_z", 5),
    ("Ym", "ch", 2),
    ("function CMs(e) {", "function QJs(e) {", 1),
    ("TMs", "eYs", 3),
    ("  EMs = e(() => {", "  tYs = n(() => {", 1),
    ("     ((eYs = c()),", "     ((eYs = l()),", 1),
    (
        "(CodexProviderPatchReact = r(o(), 1))",
        "(CodexProviderPatchReact = r(s(), 1))",
        1,
    ),
    (
        "       pd(),\n       ad(),\n       gls(),",
        "       ld(),\n       td(),\n       ETs(),",
        1,
    ),
)
PICKER_DIFF_26727 = derive_versioned_diff(PICKER_DIFF_26721, PICKER_RENAMES_26727)


CENTRAL_DIFF_V2_TO_V3 = r"""@@ -137601,7 +137601,7 @@
   };
 }
 function codexProviderRoutingState() {
-  return (window.__codexDesktopModelProvidersPatchV2 ??= {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
     config: codexProviderRoutingFallback(),
     configPath: null,
     error: null,
"""


PICKER_DIFF_26721_V2_TO_V3 = r"""@@ -520849,7 +520849,7 @@
 }
 function Scs(e) {
-  let t = (0, wcs.c)(12),
+  let t = (0, wcs.c)(13),
     { submenu: n } = e,
     r = n.ariaLabel,
     i = n.contentClassName,
@@ -520871,10 +520871,15 @@
     t[7] !== n.label ||
     t[8] !== n.value ||
     t[9] !== o ||
-    t[10] !== l
+    t[10] !== l ||
+    t[11] !== n.extras
       ? ((u = (0, QX.jsx)(Kos, {
           ariaLabel: r,
           contentClassName: i,
           disabled: a,
           flyoutHeader: o,
           label: s,
           value: c,
-          children: l,
+          children:
+            n.extras == null
+              ? l
+              : (0, QX.jsxs)(QX.Fragment, { children: [n.extras, l] }),
         })),
         (t[4] = n.ariaLabel),
         (t[5] = n.contentClassName),
@@ -520887,8 +520892,9 @@
         (t[8] = n.value),
         (t[9] = o),
         (t[10] = l),
-        (t[11] = u))
-      : (u = t[11]),
+        (t[11] = n.extras),
+        (t[12] = u))
+      : (u = t[12]),
     u
   );
 }
@@ -549630,7 +549636,7 @@
   };
 }
 function codexPickerProviderRoutingState() {
-  return (window.__codexDesktopModelProvidersPatchV2 ??= {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
     config: codexPickerProviderRoutingFallback(),
     configPath: null,
     error: null,
@@ -549886,7 +549892,6 @@
         (t[39] = f))
       : (f = t[39]),
       (G = {
-        extras: (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
         effort: {
           ariaLabel: U.formatMessage(
             {
@@ -549921,6 +549926,7 @@
           value: s,
         },
         model: {
+          extras: (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
           ariaLabel: U.formatMessage(
             {
               id: `composer.intelligenceDropdown.model.rowAriaLabel`,
@@ -550013,6 +550019,7 @@
       ? (g = t[52])
       : ((g = (0, wQ.jsxs)(wQ.Fragment, {
           children: [
+            (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
             m,
             (0, wQ.jsx)(`div`, {
               className: `vertical-scroll-fade-mask flex max-h-[250px] flex-col overflow-y-auto`,
@@ -550148,7 +550155,6 @@
       : (k = t[77]),
       (K = (0, wQ.jsxs)(wQ.Fragment, {
         children: [
-          (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
           (0, wQ.jsx)(Kos, {
             ariaLabel: U.formatMessage(
               {
@@ -550354,7 +550360,6 @@
   t[90] !== le || t[91] !== pe || t[92] !== me
     ? ((he = (0, wQ.jsxs)(wQ.Fragment, {
         children: [
-          (0, wQ.jsx)(CodexCustomProviderPickerSection, {}),
           le,
           pe,
           me,
"""


PICKER_DIFF_LEGACY_V2_TO_V3 = r"""@@ -10242,7 +10242,7 @@
   };
 }
 function codexPickerProviderRoutingState() {
-  return (window.__codexDesktopModelProvidersPatchV2 ??= {
+  return (window.__codexDesktopModelProvidersPatchV3 ??= {
     config: codexPickerProviderRoutingFallback(),
     configPath: null,
     error: null,
@@ -10360,6 +10360,6 @@
 function MO(e) {
   let t = (0, PO.c)(169),
     {
"""


PATCH_VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("ChatGPT 26.727 Power Picker", CENTRAL_DIFF_26727, PICKER_DIFF_26727),
    ("ChatGPT 26.721 Power Picker", CENTRAL_DIFF_26721, PICKER_DIFF_26721),
    ("ChatGPT 26.715 legacy picker", CENTRAL_DIFF, PICKER_DIFF),
    (
        "ChatGPT 26.721 provider-picker V2 upgrade",
        CENTRAL_DIFF_V2_TO_V3,
        PICKER_DIFF_26721_V2_TO_V3,
    ),
    (
        "ChatGPT 26.715 provider-picker V2 marker upgrade",
        CENTRAL_DIFF_V2_TO_V3,
        PICKER_DIFF_LEGACY_V2_TO_V3,
    ),
)


class PatchError(RuntimeError):
    """A safe, expected patch failure."""


def colors_enabled(stream: Any = sys.stdout) -> bool:
    return "NO_COLOR" not in os.environ and (
        getattr(stream, "isatty", lambda: False)()
        or os.environ.get("FORCE_COLOR") not in (None, "", "0")
    )


def color(text: object, *codes: str, stream: Any = sys.stdout) -> str:
    rendered = str(text)
    if not colors_enabled(stream) or not codes:
        return rendered
    return f"\033[{';'.join(codes)}m{rendered}\033[0m"


def terminal_width() -> int:
    return max(64, min(shutil.get_terminal_size((96, 24)).columns, 110))


def terminal_status(
    label: str,
    message: object,
    code: str,
    *,
    detail: object | None = None,
    stream: Any = sys.stdout,
) -> None:
    badge_width = 10
    plain_badge = f"[{label}]"
    badge = color(plain_badge, "1", code, stream=stream)
    badge_padding = " " * max(1, badge_width - len(plain_badge))
    available = max(30, terminal_width() - badge_width)
    lines = textwrap.wrap(
        str(message),
        width=available,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    print(f"{badge}{badge_padding}{lines[0]}", file=stream)
    for line in lines[1:]:
        print(f"{'':{badge_width}}{line}", file=stream)
    if detail is not None:
        detail_lines = textwrap.wrap(
            str(detail),
            width=max(30, terminal_width() - badge_width - 2),
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for index, line in enumerate(detail_lines):
            marker = "↳ " if index == 0 else "  "
            print(
                f"{'':{badge_width}}{color(marker + line, '2', stream=stream)}",
                file=stream,
            )
    stream.flush()


def terminal_heading(title: str, code: str = "36") -> None:
    visible_title = f" {title.upper()} "
    rule_length = max(2, terminal_width() - len(visible_title))
    print()
    print(
        color(f"{visible_title}{'━' * rule_length}", "1", code),
    )
    sys.stdout.flush()


def terminal_panel(
    title: str,
    message: object,
    code: str,
    *,
    stream: Any = sys.stderr,
) -> None:
    width = terminal_width()
    title_text = f" {title.upper()} "
    top = f"╭─{title_text}{'─' * max(1, width - len(title_text) - 2)}"
    bottom = f"╰{'─' * (width - 1)}"
    print(file=stream)
    print(color(top, "1", code, stream=stream), file=stream)
    paragraphs = str(message).splitlines() or [""]
    for paragraph in paragraphs:
        wrapped = textwrap.wrap(
            paragraph,
            width=max(30, width - 4),
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for line in wrapped:
            border = color("│", code, stream=stream)
            print(f"{border} {color(line, '1', stream=stream)}", file=stream)
    print(color(bottom, "1", code, stream=stream), file=stream)
    print(file=stream)
    stream.flush()


def terminal_bullet(label: str, description: str) -> None:
    bullet = color("◆", "1", "36")
    key = color(label, "1", "33")
    prefix_width = 29
    prefix = f"  {bullet} {key}"
    padding = " " * max(1, prefix_width - 4 - len(label))
    available = max(30, terminal_width() - prefix_width)
    lines = textwrap.wrap(
        description,
        width=available,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    print(f"{prefix}{padding}{lines[0]}")
    for line in lines[1:]:
        print(f"{'':{prefix_width}}{line}")
    sys.stdout.flush()


def print_completion_summary(
    config: Path,
    *,
    backup: Path | None = None,
    already_installed: bool = False,
    upgraded: bool = False,
) -> None:
    codex_config = config.parent / "config.toml"
    if already_installed:
        terminal_status(
            "READY",
            "Patch already installed; no app files were changed.",
            "32",
        )
    else:
        terminal_status(
            "SUCCESS",
            "Patch upgraded successfully."
            if upgraded
            else "Patch installed successfully.",
            "32",
        )

    terminal_heading("Custom provider config")
    terminal_status("CONFIG", "Edit this file to customize provider routing:", "36", detail=config)
    terminal_bullet("providers", "Providers displayed in the app menu.")
    terminal_bullet(
        "model_providers",
        "Maps each exact model slug to the provider used by Automatic mode.",
    )
    terminal_bullet(
        "default_provider",
        "Provider used by Automatic mode when a model has no explicit mapping.",
    )
    terminal_status(
        "LINK",
        "Custom provider IDs must match a [model_providers.<id>] section.",
        "35",
        detail=codex_config,
    )
    terminal_status(
        "KEYS",
        "Do not put API keys in the provider-routing JSON file.",
        "33",
        detail="Keep credentials in the provider authentication configuration or environment.",
    )

    terminal_heading("After editing", "35")
    terminal_status(
        "RELOAD",
        "Save valid JSON, then close and reopen the model/provider menu.",
        "35",
        detail="No repatching or app restart is needed.",
    )

    if backup is not None:
        terminal_heading("Recovery", "34")
        terminal_status("BACKUP", "Complete original app backup:", "34", detail=backup)

    terminal_heading("Important", "33")
    terminal_status(
        "NOTICE",
        "The patched Windows executable has an updated Electron integrity resource. A ChatGPT/Codex update may replace this patch.",
        "33",
    )
    print()


def fail(message: str, exit_code: int = 1) -> NoReturn:
    terminal_panel("Error", message, "31", stream=sys.stderr)
    raise SystemExit(exit_code)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    label: str | None = None,
) -> subprocess.CompletedProcess[str]:
    terminal_status(
        "STEP",
        label or f"Running {Path(command[0]).name}",
        "36",
        detail=shlex.join(command),
    )
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        output = exc.stdout.strip() if exc.stdout else ""
        if output:
            terminal_panel("Command output", output, "31", stream=sys.stderr)
        raise PatchError(f"Command failed with exit status {exc.returncode}") from exc


class FancyArgumentParser(argparse.ArgumentParser):
    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        stream = file or sys.stdout
        width = terminal_width()
        title = " COMMAND HELP "
        top = f"╭─{title}{'─' * max(1, width - len(title) - 2)}"
        bottom = f"╰{'─' * (width - 1)}"
        print(file=stream)
        print(color(top, "1", "36", stream=stream), file=stream)
        for raw_line in message.rstrip().splitlines():
            border = color("│", "36", stream=stream)
            stripped = raw_line.strip()
            if not stripped:
                print(border, file=stream)
                continue
            if raw_line.startswith("usage:"):
                label, remainder = raw_line.split(":", 1)
                rendered = (
                    color(label.upper(), "1", "35", stream=stream)
                    + color(":", "35", stream=stream)
                    + color(remainder, "1", stream=stream)
                )
            elif stripped in {"options:", "optional arguments:"}:
                rendered = color(stripped.upper(), "1", "36", stream=stream)
            elif raw_line.startswith("  -"):
                option_and_help = re.split(r"(\s{2,})", stripped, maxsplit=1)
                option = option_and_help[0]
                remainder = "".join(option_and_help[1:])
                rendered = (
                    "  "
                    + color(option, "1", "33", stream=stream)
                    + color(remainder, stream=stream)
                )
            else:
                rendered = color(raw_line, stream=stream)
            print(f"{border} {rendered}", file=stream)
        print(color(bottom, "1", "36", stream=stream), file=stream)
        print(file=stream)
        stream.flush()

    def error(self, message: str) -> NoReturn:
        terminal_panel("Argument error", message, "31", stream=sys.stderr)
        terminal_status(
            "HELP",
            "Show all installer options with:",
            "33",
            detail=f"{self.prog} --help",
            stream=sys.stderr,
        )
        self.exit(2)


def invoking_user_home() -> Path:
    """Return the interactive Windows user profile directory."""
    return Path(os.environ.get("USERPROFILE") or Path.home())

def default_backup_dir(home: Path) -> Path:
    return home / "Applications" / "ChatGPT Patch Backups"


def common_windows_app_roots() -> list[Path]:
    roots: list[Path] = []
    for env_name in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))
    roots.append(Path(r"C:\Program Files\WindowsApps"))
    return list(dict.fromkeys(roots))


def find_chatgpt_installations() -> list[Path]:
    """Locate likely Windows ChatGPT/Codex Electron install roots."""
    roots: list[Path] = []
    patterns = (
        "OpenAI.Codex*",
        "OpenAI.ChatGPT*",
        "ChatGPT*",
        "Codex*",
        "chatgpt*",
        "codex*",
    )
    for base in common_windows_app_roots():
        if not base.is_dir():
            continue
        try:
            children = list(base.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir() and any(fnmatch.fnmatch(child.name, pat) for pat in patterns):
                for candidate in (child, child / "app"):
                    if (candidate / "resources" / "app.asar").is_file():
                        roots.append(candidate)
    return sorted(dict.fromkeys(roots), key=lambda path: str(path).lower())


def default_app_path() -> Path:
    found = find_chatgpt_installations()
    if found:
        return found[0]
    return Path(r"C:\Program Files\WindowsApps\OpenAI.Codex_UNKNOWN\app")


def parse_args() -> argparse.Namespace:
    home = invoking_user_home()
    configured_codex_home = os.environ.get("CODEX_HOME")
    codex_home = (
        Path(configured_codex_home).expanduser()
        if configured_codex_home
        else home / ".codex"
    )
    parser = FancyArgumentParser(
        description=(
            "Add a dynamic provider selector and per-model provider routing to the "
            "Windows ChatGPT/Codex desktop app."
        )
    )
    parser.add_argument(
        "--app",
        type=Path,
        default=default_app_path(),
        help="Install root containing resources\\app.asar (auto-detected when possible)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=codex_home / "desktop-model-providers.json",
        help="Provider-routing JSON file in the effective Codex home",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=default_backup_dir(home),
        help="Directory in which a complete app backup is created",
    )
    parser.add_argument(
        "--overwrite-config",
        action="store_true",
        help="Replace the provider-routing JSON with the built-in template",
    )
    parser.add_argument(
        "--allow-running",
        action="store_true",
        help="Do not close target-app processes before patching (unsafe)",
    )
    return parser.parse_args()

def validate_provider_config(data: Any) -> None:
    if not isinstance(data, dict):
        raise PatchError("Provider config must be a JSON object")
    if data.get("version") != 1:
        raise PatchError("Provider config version must be 1")
    providers = data.get("providers")
    if not isinstance(providers, list) or not providers:
        raise PatchError("Provider config 'providers' must be a non-empty array")

    provider_ids: set[str] = set()
    for provider in providers:
        if not isinstance(provider, dict):
            raise PatchError("Every provider must be an object")
        provider_id = provider.get("id")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise PatchError("Every provider id must be a non-empty string")
        provider_id = provider_id.strip()
        if provider_id in provider_ids:
            raise PatchError(f"Duplicate provider id: {provider_id}")
        provider_ids.add(provider_id)
        label = provider.get("label")
        if not isinstance(label, str) or not label.strip():
            raise PatchError(f"Provider '{provider_id}' needs a non-empty label")
        description = provider.get("description", "")
        if not isinstance(description, str):
            raise PatchError(f"Provider '{provider_id}' description must be a string")

    default_provider = data.get("default_provider")
    if default_provider not in provider_ids:
        raise PatchError("default_provider must reference a configured provider")

    mappings = data.get("model_providers")
    if not isinstance(mappings, dict):
        raise PatchError("model_providers must be an object")
    for model, provider_id in mappings.items():
        if not isinstance(model, str) or not model.strip():
            raise PatchError("Every model mapping key must be a non-empty string")
        if provider_id not in provider_ids:
            raise PatchError(
                f"Model '{model}' references unknown provider '{provider_id}'"
            )


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ensure_provider_config(path: Path, overwrite: bool) -> str:
    if overwrite or not path.exists() or path.stat().st_size == 0:
        validate_provider_config(DEFAULT_PROVIDER_CONFIG)
        atomic_write_json(path, DEFAULT_PROVIDER_CONFIG)
        return "written"
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchError(f"Cannot read valid JSON from {path}: {exc}") from exc
    validate_provider_config(data)
    return "kept"


def asar_header_hash(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            size_pickle = handle.read(8)
            if len(size_pickle) != 8:
                raise PatchError("ASAR archive is too short to contain a header")
            size_payload, header_pickle_size = struct.unpack("<II", size_pickle)
            if size_payload != 4 or header_pickle_size < 8:
                raise PatchError("ASAR archive has an invalid header-size pickle")

            header_pickle = handle.read(header_pickle_size)
            if len(header_pickle) != header_pickle_size:
                raise PatchError("ASAR archive contains a truncated header")
    except OSError as exc:
        raise PatchError(f"Cannot read ASAR header from {path}: {exc}") from exc

    header_payload_size, header_string_size = struct.unpack("<II", header_pickle[:8])
    if header_payload_size > header_pickle_size - 4:
        raise PatchError("ASAR header payload size is invalid")
    header_start = 8
    header_end = header_start + header_string_size
    if header_end > len(header_pickle):
        raise PatchError("ASAR header string is truncated")

    header_json = header_pickle[header_start:header_end]
    try:
        json.loads(header_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatchError("ASAR header does not contain valid UTF-8 JSON") from exc
    return hashlib.sha256(header_json).hexdigest()


def contains_marker(path: Path, marker: bytes = PATCH_MARKER) -> bool:
    overlap = len(marker) - 1
    previous = b""
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            data = previous + chunk
            if marker in data:
                return True
            previous = data[-overlap:] if overlap else b""
    return False


def load_windows_integrity(executable: Path) -> list[dict[str, Any]]:
    """Read Electron's Windows ASAR integrity resource from the app executable."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    kernel32.LoadLibraryExW.restype = wintypes.HMODULE
    kernel32.FindResourceExW.argtypes = [wintypes.HMODULE, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.WORD]
    kernel32.FindResourceExW.restype = wintypes.HRSRC
    kernel32.LoadResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
    kernel32.LoadResource.restype = wintypes.HGLOBAL
    kernel32.LockResource.argtypes = [wintypes.HGLOBAL]
    kernel32.LockResource.restype = wintypes.LPVOID
    kernel32.SizeofResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
    kernel32.SizeofResource.restype = wintypes.DWORD
    kernel32.FreeLibrary.argtypes = [wintypes.HMODULE]
    module = kernel32.LoadLibraryExW(str(executable), None, 0x00000002)
    if not module:
        raise PatchError(f"Cannot load executable resources from {executable}: Windows error {ctypes.get_last_error()}")
    try:
        resource = kernel32.FindResourceExW(module, WINDOWS_INTEGRITY_TYPE, WINDOWS_INTEGRITY_NAME, WINDOWS_RESOURCE_LANG)
        if not resource:
            resource = kernel32.FindResourceExW(module, WINDOWS_INTEGRITY_TYPE, WINDOWS_INTEGRITY_NAME, 0)
        if not resource:
            raise PatchError("Executable has no Electron ASAR integrity resource")
        loaded = kernel32.LoadResource(module, resource)
        pointer = kernel32.LockResource(loaded)
        size = kernel32.SizeofResource(module, resource)
        raw = ctypes.string_at(pointer, size)
    finally:
        kernel32.FreeLibrary(module)
    try:
        data = json.loads(raw.decode("utf-8-sig").rstrip("\x00"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatchError("Electron ASAR integrity resource is not valid JSON") from exc
    if not isinstance(data, list):
        raise PatchError("Electron ASAR integrity resource must be a JSON array")
    return data


def write_windows_integrity(executable: Path, entries: list[dict[str, Any]]) -> None:
    """Atomically update Electron's Windows ASAR integrity resource."""
    payload = json.dumps(entries, separators=(",", ":")).encode("utf-8")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel32.UpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.WORD, wintypes.LPVOID, wintypes.DWORD]
    kernel32.UpdateResourceW.restype = wintypes.BOOL
    kernel32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    kernel32.EndUpdateResourceW.restype = wintypes.BOOL
    handle = kernel32.BeginUpdateResourceW(str(executable), False)
    if not handle:
        raise PatchError(f"Cannot begin resource update for {executable}: Windows error {ctypes.get_last_error()}")
    buffer = ctypes.create_string_buffer(payload)
    ok = kernel32.UpdateResourceW(handle, WINDOWS_INTEGRITY_TYPE, WINDOWS_INTEGRITY_NAME, WINDOWS_RESOURCE_LANG, buffer, len(payload))
    if not ok:
        error = ctypes.get_last_error()
        kernel32.EndUpdateResourceW(handle, True)
        raise PatchError(f"Cannot update Electron ASAR integrity resource: Windows error {error}")
    if not kernel32.EndUpdateResourceW(handle, False):
        raise PatchError(f"Cannot commit Electron ASAR integrity resource: Windows error {ctypes.get_last_error()}")




def asar_integrity_hash(entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        if (
            isinstance(entry, dict)
            and str(entry.get("file", "")).replace("/", "\\").lower()
            == r"resources\app.asar"
        ):
            value = entry.get("value")
            if isinstance(value, str):
                return value.lower()
    raise PatchError("Executable has no resources\\app.asar integrity entry")

def app_path_variants(app: Path) -> set[str]:
    variants = {str(app), str(app.resolve())}
    return {value.rstrip("\\/").lower() for value in variants}

def find_target_app_processes(app: Path) -> list[tuple[int, str]]:
    prefixes = tuple(f"{variant}\\" for variant in app_path_variants(app))
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        terminal_status("WARNING", "PowerShell was not found; running-process detection is limited.", "33")
        return []
    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PatchError(f"Could not inspect running processes: {exc}") from exc
    if not result.stdout.strip():
        return []
    data = json.loads(result.stdout)
    rows = data if isinstance(data, list) else [data]
    matches: list[tuple[int, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        executable_path = str(row.get("ExecutablePath") or "").rstrip("\\/").lower()
        command_line = str(row.get("CommandLine") or executable_path)
        try:
            pid = int(row.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        probe = executable_path + "\\" if executable_path else command_line.lower()
        if pid != os.getpid() and any(probe.startswith(prefix) for prefix in prefixes):
            matches.append((pid, command_line))
    return matches

def signal_processes(processes: list[tuple[int, str]], signal_number: int) -> None:
    for pid, _command in processes:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T"] + (["/F"] if signal_number else []), check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as exc:
            output = exc.stdout or ""
            if "not found" not in output.lower():
                raise PatchError(f"Could not stop process {pid}: {output.strip()}") from exc

def wait_for_app_processes_to_exit(app: Path, timeout: float) -> list[tuple[int, str]]:
    deadline = time.monotonic() + timeout
    remaining = find_target_app_processes(app)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.2)
        remaining = find_target_app_processes(app)
    return remaining


def stop_target_app_processes(app: Path, allow_running: bool) -> None:
    executable = find_app_executable(app)
    if not executable.is_file():
        raise PatchError(f"Cannot identify the target ChatGPT/Codex executable: {executable}")

    processes = find_target_app_processes(app)
    if not processes:
        terminal_status(
            "PROCESS",
            "The target ChatGPT app is not running.",
            "32",
            detail=app,
        )
        return

    pid_summary = ", ".join(str(pid) for pid, _command in processes)
    if allow_running:
        terminal_status(
            "WARNING",
            "Target-app processes are running, but automatic closing was disabled.",
            "33",
            detail=f"PIDs: {pid_summary}",
        )
        return

    terminal_status(
        "CLOSE",
        f"Closing {len(processes)} process(es) launched from the target app bundle.",
        "35",
        detail=f"PIDs: {pid_summary}",
    )
    signal_processes(processes, 0)
    remaining = wait_for_app_processes_to_exit(app, 5.0)

    if remaining:
        remaining_pids = ", ".join(str(pid) for pid, _command in remaining)
        terminal_status(
            "FORCE",
            "Some target-app processes ignored the close request; force-closing them.",
            "33",
            detail=f"PIDs: {remaining_pids}",
        )
        signal_processes(remaining, 1)
        remaining = wait_for_app_processes_to_exit(app, 3.0)

    if remaining:
        details = "\n".join(f"PID {pid}: {command}" for pid, command in remaining)
        raise PatchError(
            "Could not stop every process belonging to the target app bundle.\n\n"
            f"{details}"
        )

    terminal_status(
        "CLOSED",
        "All processes belonging to the target app bundle have stopped.",
        "32",
    )


def unique_candidate(
    assets: Path,
    content_needles: tuple[str, ...],
    role: str,
) -> Path:
    candidates = sorted(
        path
        for path in assets.glob("*.js")
        if not path.name.endswith(".map.js")
    )
    matches = []
    for path in candidates:
        source = path.read_text(encoding="utf-8")
        if all(needle in source for needle in content_needles):
            matches.append(path)
    if len(matches) != 1:
        raise PatchError(
            f"Expected exactly one {role} JavaScript bundle containing all "
            f"required source markers, found {len(matches)} among "
            f"{len(candidates)} JavaScript bundles"
        )
    return matches[0]


def parse_hunks(unified_diff: str) -> list[list[str]]:
    lines = unified_diff.splitlines()
    hunks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if line.startswith("@@ "):
            current = []
            hunks.append(current)
        elif current is not None:
            if not line or line[0] not in " +-":
                raise PatchError(f"Malformed embedded diff line: {line!r}")
            current.append(line)
    if not hunks:
        raise PatchError("Embedded patch contains no hunks")
    return hunks


def render_unified_diff(source: str, unified_diff: str, source_name: str) -> str:
    had_trailing_newline = source.endswith("\n")
    source_lines = source.splitlines()
    search_start = 0

    for hunk_number, hunk in enumerate(parse_hunks(unified_diff), start=1):
        old_lines = [line[1:] for line in hunk if line[0] in " -"]
        new_lines = [line[1:] for line in hunk if line[0] in " +"]
        matches = [
            index
            for index in range(search_start, len(source_lines) - len(old_lines) + 1)
            if source_lines[index : index + len(old_lines)] == old_lines
        ]
        if len(matches) != 1:
            raise PatchError(
                f"{source_name}: hunk {hunk_number} matched {len(matches)} times; "
                "the app build is unsupported or already modified"
            )
        index = matches[0]
        source_lines[index : index + len(old_lines)] = new_lines
        search_start = index + len(new_lines)

    return "\n".join(source_lines) + ("\n" if had_trailing_newline else "")


def apply_supported_patch_variant(central: Path, picker: Path) -> str:
    originals = {
        path: path.read_text(encoding="utf-8") for path in {central, picker}
    }
    compatible: list[tuple[str, dict[Path, str]]] = []

    for name, central_diff, picker_diff in PATCH_VARIANTS:
        rendered = originals.copy()
        try:
            rendered[central] = render_unified_diff(
                rendered[central], central_diff, central.name
            )
            rendered[picker] = render_unified_diff(
                rendered[picker], picker_diff, picker.name
            )
        except PatchError:
            continue
        compatible.append((name, rendered))

    if len(compatible) != 1:
        raise PatchError(
            "Expected exactly one supported JavaScript patch layout, found "
            f"{len(compatible)}. This app build is unsupported or already modified."
        )

    name, rendered = compatible[0]
    for path, source in rendered.items():
        path.write_text(source, encoding="utf-8")
    return name


def make_backup(app: Path, backup_dir: Path, version: str, build: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version)
    safe_build = re.sub(r"[^A-Za-z0-9._-]+", "-", build)
    backup = backup_dir / f"ChatGPT-{safe_version}-build-{safe_build}-{timestamp}"
    suffix = 1
    while backup.exists():
        backup = backup_dir / f"ChatGPT-{safe_version}-build-{safe_build}-{timestamp}-{suffix}"
        suffix += 1
    terminal_status("STEP", "Creating a complete app backup", "36", detail=f"copytree {app} {backup}")
    shutil.copytree(app, backup, copy_function=shutil.copy2)
    if not (backup / "resources" / "app.asar").is_file():
        raise PatchError(f"Backup verification failed: {backup}")
    return backup

def atomic_replace_file(source: Path, target: Path) -> None:
    original_stat = target.stat()
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.patch-", dir=target.parent)
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary_path)
        os.chmod(temporary_path, original_stat.st_mode)
        os.replace(temporary_path, target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

def restore_backup(app: Path, backup: Path) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    failed_copy = app.with_name(f"{app.name}.patch-failed-{timestamp}")
    suffix = 1
    while failed_copy.exists():
        failed_copy = app.with_name(f"{app.name}.patch-failed-{timestamp}-{suffix}")
        suffix += 1
    os.replace(app, failed_copy)
    try:
        terminal_status("STEP", "Restoring the original app from backup", "36", detail=f"copytree {backup} {app}")
        shutil.copytree(backup, app, copy_function=shutil.copy2)
    except Exception:
        os.replace(failed_copy, app)
        raise
    return failed_copy


def find_app_executable(app: Path) -> Path:
    preferred = ("Codex.exe", "ChatGPT.exe")
    for name in preferred:
        candidate = app / name
        if candidate.is_file():
            return candidate
    exes = sorted(app.glob("*.exe"))
    if len(exes) == 1:
        return exes[0]
    for exe in exes:
        if exe.stem.lower() in {"codex", "chatgpt"}:
            return exe
    return app / "Codex.exe"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def patch_app(app: Path, config: Path, backup_dir: Path, overwrite_config: bool) -> None:
    resources = app / "resources"
    asar_path = resources / "app.asar"
    unpacked_path = resources / "app.asar.unpacked"
    executable = find_app_executable(app)

    if sys.platform != "win32":
        raise PatchError("This installer only supports Windows")
    if not app.is_dir() or not executable.is_file() or not asar_path.is_file():
        raise PatchError(f"Not a supported Windows ChatGPT/Codex install root: {app}")
    if not unpacked_path.is_dir():
        raise PatchError(f"Missing ASAR companion directory: {unpacked_path}")
    if shutil.which("npx") is None:
        raise PatchError("npx is required. Install Node.js, then run this installer again")
    if "WindowsApps" in str(app) and not is_admin():
        terminal_status(
            "WARNING",
            "This looks like a Microsoft Store package under WindowsApps; administrator rights or adjusted file permissions may be required.",
            "33",
            detail=app,
        )

    config_action = ensure_provider_config(config, overwrite_config)
    terminal_status(
        "CONFIG",
        "Provider-routing config created."
        if config_action == "written"
        else "Existing provider-routing config validated.",
        "36",
        detail=config,
    )

    integrity = load_windows_integrity(executable)
    version = "unknown"
    build = "unknown"
    for probe in (app.parent.name, app.name):
        match = re.search(r"_(\d+(?:\.\d+)+)_", probe)
        if match:
            version = match.group(1)
            build = match.group(1)
            break
    if contains_marker(asar_path):
        terminal_status("APP", f"Detected ChatGPT/Codex {version}, build {build}.", "34", detail=app)
        print_completion_summary(config, already_installed=True)
        return

    is_upgrade = contains_marker(asar_path, LEGACY_PATCH_MARKER)
    if is_upgrade:
        terminal_status("UPGRADE", "An earlier provider-picker patch was detected and will be upgraded.", "35", detail=f"ChatGPT/Codex {version}, build {build}")

    current_header_hash = asar_header_hash(asar_path)
    expected_header_hash = asar_integrity_hash(integrity)
    if current_header_hash != expected_header_hash:
        raise PatchError("The ASAR header does not match the executable's Electron integrity resource. The installation may be incomplete or modified.")
    terminal_status("VERIFY", "The original app's ASAR header integrity is valid.", "32", detail=current_header_hash)

    terminal_heading("Installation", "35")
    terminal_status("APP", f"Preparing ChatGPT/Codex {version}, build {build}.", "34", detail=app)
    with tempfile.TemporaryDirectory(prefix="chatgpt-provider-patch-") as temporary:
        work = Path(temporary)
        extracted = work / "app"
        patched_asar = work / "app.asar"
        patched_executable = work / executable.name

        run(["npx", "--yes", ASAR_PACKAGE, "extract", str(asar_path), str(extracted)], label="Extracting application resources")
        assets = extracted / "webview" / "assets"
        if not assets.is_dir():
            raise PatchError("Extracted app has no webview/assets directory")

        central = unique_candidate(assets, ("async prewarmThreadStart(", "async sendConfigReadRequest("), "App Server client")
        picker = unique_candidate(assets, ("composer.intelligenceDropdown.tooltip", "modelOptionsDisabled"), "model picker")
        patch_targets = list(dict.fromkeys((central, picker)))

        run(["npx", "--yes", PRETTIER_PACKAGE, "--write", *(str(path) for path in patch_targets)], label="Preparing the JavaScript bundles")
        patch_layout = apply_supported_patch_variant(central, picker)
        terminal_status("LAYOUT", "Matched a supported application bundle layout.", "32", detail=patch_layout)

        if PATCH_MARKER.decode() not in central.read_text(encoding="utf-8"):
            raise PatchError("Routing marker missing after patch")
        if "CodexCustomProviderPickerSection" not in picker.read_text(encoding="utf-8"):
            raise PatchError("Provider picker missing after patch")

        run(["npx", "--yes", PRETTIER_PACKAGE, "--write", *(str(path) for path in patch_targets)], label="Formatting and validating the patched JavaScript")
        run(["npx", "--yes", ASAR_PACKAGE, "pack", str(extracted), str(patched_asar)], label="Packing patched application resources")

        if not contains_marker(patched_asar):
            raise PatchError("Packed ASAR does not contain the patch marker")
        if contains_marker(patched_asar, LEGACY_PATCH_MARKER):
            raise PatchError("Packed ASAR still contains the legacy patch marker")
        patched_header_hash = asar_header_hash(patched_asar)
        patched_integrity = [dict(entry) if isinstance(entry, dict) else entry for entry in integrity]
        updated = False
        for entry in patched_integrity:
            if isinstance(entry, dict) and str(entry.get("file", "")).replace("/", "\\").lower() == r"resources\app.asar":
                entry["alg"] = "sha256"
                entry["value"] = patched_header_hash
                updated = True
        if not updated:
            raise PatchError("Could not update resources\\app.asar integrity entry")
        shutil.copy2(executable, patched_executable)
        write_windows_integrity(patched_executable, patched_integrity)

        backup = make_backup(app, backup_dir, version, build)
        terminal_status("OK", "App backup created.", "32", detail=backup)

        live_mutation_started = False
        try:
            live_mutation_started = True
            atomic_replace_file(patched_asar, asar_path)
            atomic_replace_file(patched_executable, executable)
            final_integrity = load_windows_integrity(executable)
            if asar_header_hash(asar_path) != asar_integrity_hash(final_integrity):
                raise PatchError("Installed ASAR integrity verification failed")
            if not contains_marker(asar_path):
                raise PatchError("Installed ASAR is missing the patch marker")
            if contains_marker(asar_path, LEGACY_PATCH_MARKER):
                raise PatchError("Installed ASAR still contains the legacy patch marker")
        except Exception as exc:
            if live_mutation_started:
                terminal_status("RECOVERY", "Installation failed after app files changed. Restoring the backup.", "33", stream=sys.stderr)
                try:
                    failed_copy = restore_backup(app, backup)
                    terminal_status("RESTORED", "The original app was restored. The failed patched copy was retained.", "32", detail=failed_copy, stream=sys.stderr)
                except Exception as restore_exc:
                    terminal_panel("Recovery failed", f"Automatic restoration failed: {restore_exc}\nThe full backup remains at: {backup}", "31", stream=sys.stderr)
            raise exc

    print_completion_summary(config, backup=backup, upgraded=is_upgrade)

def main() -> int:
    args = parse_args()
    try:
        app = args.app.expanduser().resolve()
        stop_target_app_processes(app, args.allow_running)
        patch_app(
            app,
            args.config.expanduser().resolve(),
            args.backup_dir.expanduser().resolve(),
            args.overwrite_config,
        )
    except PatchError as exc:
        fail(str(exc))
    except PermissionError as exc:
        fail(f"Permission denied: {exc}")
    except KeyboardInterrupt:
        fail("Interrupted", 130)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
