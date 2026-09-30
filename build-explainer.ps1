# Rebuilds docs/vidx_explainer.pdf from vidx_explainer.md.
#
# Requires pandoc and a XeLaTeX install (MiKTeX). Run from anywhere:
#   pwsh docs/build-explainer.ps1
#
# Two non-obvious details this script exists to remember:
#   * --shift-heading-level-by=-1  : the markdown starts at "##", and the LaTeX
#     template only defines formats for \section and \subsection. Without the
#     shift, "###" becomes \subsubsection and the build dies with
#     "titlesec Error: No format for this command."
#   * the working directory must be docs/, because the template's cover page
#     pulls in ../ico/vidx-icon-1024.png by relative path.

$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '.')
try {
    pandoc vidx_explainer.md `
        --template=pandoc-template.latex `
        --pdf-engine=xelatex `
        --shift-heading-level-by=-1 `
        --metadata title="VIDX — Turn Your Scripture App Into Videos" `
        -o vidx_explainer.pdf
    if ($LASTEXITCODE -ne 0) { throw "pandoc failed with exit code $LASTEXITCODE" }
    $pdf = Get-Item vidx_explainer.pdf
    Write-Host ("[+] Built {0} ({1:N0} KB)" -f $pdf.Name, ($pdf.Length / 1KB))
}
finally {
    Pop-Location
}
