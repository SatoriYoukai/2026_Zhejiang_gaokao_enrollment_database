# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['tools\\estimate_volunteer_landing_portable.py'],
    pathex=[],
    binaries=[],
    datas=[('data\\rank_model_database.csv', 'data')],
    hiddenimports=['openpyxl', 'xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas',
        'numpy',
        'lxml',
        'PIL',
        'scipy',
        'matplotlib',
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'sklearn',
        'numba',
        'llvmlite',
        'onnxruntime',
        'gradio',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='志愿落点概率估算器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='志愿落点概率估算器',
)
