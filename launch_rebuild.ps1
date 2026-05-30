$py     = "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\venv\Scripts\python.exe"
$script = "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\rebuild_13f_cache.py"
$log    = "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\rebuild_13f_log.txt"
$err    = "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\rebuild_13f_err.txt"
$cwd    = "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"

$proc = Start-Process -FilePath $py `
    -ArgumentList "-X utf8 -u `"$script`"" `
    -RedirectStandardOutput $log `
    -RedirectStandardError $err `
    -WorkingDirectory $cwd `
    -WindowStyle Hidden `
    -PassThru

Write-Host ("Rebuild 13F avviato - PID: " + $proc.Id)
