param(
    [string]$OutputDirectory = (Join-Path $env:LOCALAPPDATA 'VideoToObsidian\quality-fixtures')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$ffprobe = (Get-Command ffprobe -ErrorAction Stop).Source
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Speech

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$work = Join-Path $OutputDirectory 'build'
if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}
New-Item -ItemType Directory -Path $work -Force | Out-Null

function Write-Card {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Heading,
        [Parameter(Mandatory)][string[]]$Lines,
        [Parameter(Mandatory)][string]$Accent
    )

    $bitmap = New-Object System.Drawing.Bitmap 1280, 720
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $background = [System.Drawing.ColorTranslator]::FromHtml('#10131A')
    $accentColor = [System.Drawing.ColorTranslator]::FromHtml($Accent)
    $foreground = [System.Drawing.ColorTranslator]::FromHtml('#F5F7FA')
    $muted = [System.Drawing.ColorTranslator]::FromHtml('#B7C0CE')
    $graphics.Clear($background)

    $accentBrush = New-Object System.Drawing.SolidBrush $accentColor
    $foregroundBrush = New-Object System.Drawing.SolidBrush $foreground
    $mutedBrush = New-Object System.Drawing.SolidBrush $muted
    $headingFont = New-Object System.Drawing.Font 'Microsoft YaHei', 42, ([System.Drawing.FontStyle]::Bold)
    $bodyFont = New-Object System.Drawing.Font 'Microsoft YaHei', 29, ([System.Drawing.FontStyle]::Regular)
    try {
        $graphics.FillRectangle($accentBrush, 72, 76, 18, 568)
        $graphics.DrawString($Heading, $headingFont, $foregroundBrush, 126, 88)
        $y = 200
        foreach ($line in $Lines) {
            $graphics.DrawString($line, $bodyFont, $mutedBrush, 130, $y)
            $y += 76
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $headingFont.Dispose()
        $bodyFont.Dispose()
        $accentBrush.Dispose()
        $foregroundBrush.Dispose()
        $mutedBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Write-Speech {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Rate,
        [Parameter(Mandatory)][string]$Pitch
    )

    $synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $voice = @($synthesizer.GetInstalledVoices() | Where-Object {
            $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-CN'
        }) | Select-Object -First 1
        if ($null -eq $voice) {
            throw '没有找到可用的 zh-CN Windows 语音。'
        }
        $escaped = [System.Security.SecurityElement]::Escape($Text)
        $voiceName = [System.Security.SecurityElement]::Escape($voice.VoiceInfo.Name)
        $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'><voice name='$voiceName'><prosody rate='$Rate' pitch='$Pitch'>$escaped</prosody></voice></speak>"
        $synthesizer.SetOutputToWaveFile($Path)
        $synthesizer.SpeakSsml($ssml)
    }
    finally {
        $synthesizer.Dispose()
    }
}

$segments = @(
    [ordered]@{
        id = 'speaker-a'
        heading = '发言人甲 · 陈岚'
        lines = @('立场：远程办公能提高专注度', '依据：减少通勤与开放办公室干扰')
        speech = '我是陈岚。我支持每周三天远程办公，因为减少通勤和办公室干扰后，团队能把更多时间用于深度工作。'
        rate = '-5%'
        pitch = '+8%'
        accent = '#51D6A9'
        expected = '笔记必须把支持远程办公的观点归属于陈岚。'
    },
    [ordered]@{
        id = 'speaker-b'
        heading = '发言人乙 · 周凯'
        lines = @('立场：反对固定三天远程办公', '依据：新人协作与反馈速度下降')
        speech = '我是周凯。我反对固定三天远程办公。新人需要高频反馈，远程沟通会让问题暴露得更晚。'
        rate = '+3%'
        pitch = '-12%'
        accent = '#6EA8FF'
        expected = '笔记必须把反对意见归属于周凯，不得与陈岚的立场合并。'
    },
    [ordered]@{
        id = 'sarcasm'
        heading = '反讽语境'
        lines = @('字面：“这个发布流程真稳定”', '事实：连续发布三次，连续崩溃三次', '实际含义：发布流程很不可靠')
        speech = '这个发布流程真是太稳定了。连续发布三次，连续崩溃三次，实在让人放心。'
        rate = '-8%'
        pitch = '+4%'
        accent = '#FFB45E'
        expected = '笔记必须识别为反讽或至少标注疑似反讽，不能写成作者认可稳定性。'
    },
    [ordered]@{
        id = 'modality-conflict'
        heading = '音频与画面冲突'
        lines = @('旁白：实验准确率为 92%', '屏幕数据：实验准确率为 29%', '要求：保留差异，不替视频裁决真假')
        speech = '实验组本轮的准确率是百分之九十二。请以旁白数字为准。'
        rate = '0%'
        pitch = '0%'
        accent = '#FF6B81'
        expected = '笔记必须同时保留 92% 与 29%，明确指出旁白和屏幕数据冲突。'
    },
    [ordered]@{
        id = 'quote-versus-position'
        heading = '引用不等于本人立场'
        lines = @('老板原话：“速度比质量重要”', '主持人立场：反对该说法', '结论：质量底线不能牺牲')
        speech = '老板的原话是，速度比质量重要。这里我只是在引用。我不同意这个说法，质量底线不能为了赶进度而牺牲。'
        rate = '-2%'
        pitch = '+2%'
        accent = '#B48CFF'
        expected = '笔记必须区分老板的被引用观点与主持人的反对立场。'
    }
)

$clips = New-Object System.Collections.Generic.List[string]
foreach ($segment in $segments) {
    $image = Join-Path $work ($segment.id + '.png')
    $audio = Join-Path $work ($segment.id + '.wav')
    $clip = Join-Path $work ($segment.id + '.mp4')
    Write-Card -Path $image -Heading $segment.heading -Lines $segment.lines -Accent $segment.accent
    Write-Speech -Path $audio -Text $segment.speech -Rate $segment.rate -Pitch $segment.pitch
    & $ffmpeg -hide_banner -loglevel error -y -loop 1 -framerate 25 -i $image -i $audio `
        -vf 'scale=1280:720,format=yuv420p' -c:v libx264 -preset medium -tune stillimage `
        -c:a aac -b:a 128k -af 'apad=pad_dur=1' -shortest $clip
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $clip)) {
        throw "ffmpeg 无法生成固定集片段：$($segment.id)"
    }
    $clips.Add($clip)
}

$concatFile = Join-Path $work 'concat.txt'
$concatLines = @($clips | ForEach-Object { "file '$($_.Replace("'", "''"))'" })
[System.IO.File]::WriteAllLines(
    $concatFile,
    $concatLines,
    (New-Object System.Text.UTF8Encoding($false))
)
$output = Join-Path $OutputDirectory 'quality-fixed-set-v1.mp4'
& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concatFile -c copy $output
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output)) {
    throw 'ffmpeg 无法合并质量固定集。'
}

$duration = [double](& $ffprobe -v error -show_entries format=duration -of 'default=noprint_wrappers=1:nokey=1' $output)
$manifest = [ordered]@{
    schema_version = 1
    fixture = 'quality-fixed-set-v1'
    generated_at = [DateTimeOffset]::Now.ToString('o')
    media = $output
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant()
    bytes = (Get-Item -LiteralPath $output).Length
    duration_seconds = [math]::Round($duration, 3)
    paid_call_performed = $false
    segments = @($segments | ForEach-Object {
        [ordered]@{ id = $_.id; expected = $_.expected }
    })
}
$manifestPath = Join-Path $OutputDirectory 'quality-fixed-set-v1.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6
