try {
    $desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
    $file = Get-ChildItem -Path $desktopPath -Filter "*check logic*" | Select-Object -First 1
    if (-not $file) {
        # Check OneDrive Desktop
        $onedriveDesktop = [System.IO.Path]::Combine($env:USERPROFILE, "OneDrive", "Desktop")
        $file = Get-ChildItem -Path $onedriveDesktop -Filter "*check logic*" | Select-Object -First 1
    }
    
    if (-not $file) {
        Write-Error "File not found on Desktop"
        exit 1
    }
    
    Write-Host "Found file: $($file.FullName)"
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Open($file.FullName)
    $text = $doc.Content.Text
    $text | Out-File "d:\Qlib-Vnstock\experiments\scratch\desktop_word_content.txt" -Encoding utf8
    $doc.Close()
    $word.Quit()
    Write-Host "SUCCESS"
} catch {
    Write-Error $_.Exception.Message
}
