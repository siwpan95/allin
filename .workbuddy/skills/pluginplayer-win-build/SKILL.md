---
name: pluginplayer-win-build
description: "Build the PluginPlayer Windows binary (siwpan/pluginplayer) from source on a fresh or migrated machine: pick the ABI-matching MinGW-w64 toolchain, prepare vendor/ (SDL3 + FFmpeg + stb + libass), run build.py --release, verify with the repo's own mechanical gates plus a headless selftest, then publish the dist/ as a Gitee release with tools/gitee_release.py. Use when the player exe is missing, when the repo moved to a new drive/machine, when a clean dist/ must be produced, or when a new release must be pushed to Gitee."
description_zh: "在全新/迁移后的机器上从源码构建 PluginPlayer（Windows），并把构建产物发成 Gitee 发行版"
agent_created: true
---

# PluginPlayer Windows 从源码构建

## 何时用
- `pluginplayer.exe` 缺失，或消费方（如 private-radio-stations 的 launcher/monitor 插件）报「播放器不存在」。
- 仓库换机器/换盘符后 `build.py` 跑不起来。
- 需要一份完整的 `dist/`（11 个插件 + libass 字幕栈）。

## 关键判断：工具链 ABI 必须与目标一致
先看**已有的、能跑通的** dist，用 PE 导入表反推工具链（不要靠猜）：

```bash
# 含 api-ms-win-crt-* → UCRT 工具链；含 msvcrt.dll → MSVCRT 工具链
grep -qa "api-ms-win-crt" libstdc++-6.dll && echo UCRT
ls libwinpthread-1.dll      # 存在 → posix 线程模型
ls libgcc_s_seh-1.dll       # 存在 → SEH 异常
```
本例结论：**x86_64 + UCRT + posix + SEH**。

## 步骤 1：装 MinGW-w64
WinLibs 免安装包（**不要**带 llvm 的那种，体积大一倍）：
```
# 从 GitHub API 挑资产（tag 形如 15.2.0posix-14.0.0-ucrt-r7）
curl -s "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases?per_page=100"
# 下载 winlibs-x86_64-posix-seh-gcc-<ver>-mingw-w64ucrt-<ver>-r<rev>.zip 后：
7z.exe x winlibs-mingw.zip -oC:\ -y      # 包内顶层就是 mingw64/ → 得到 C:\mingw64\bin\g++.exe
```
验证：`C:\mingw64\bin\g++.exe --version` 应打印 `x86_64-ucrt-posix-seh`。

## 步骤 2：7-Zip（fetch_deps.py 硬依赖）
脚本会找 `C:\Program Files\7-Zip\7z.exe` 或 PATH 里的 `7z`。**无需系统安装**——
官方安装包是 7z SFX，用免安装的 `7zr.exe` 就能把完整 7-Zip 抽出来：
```bash
curl -Lo 7zr.exe https://www.7-zip.org/a/7zr.exe
curl -Lo 7z-inst.exe https://www.7-zip.org/a/7z2603-x64.exe
./7zr.exe x 7z-inst.exe -o7zip-full -y     # → 7z.exe + 7z.dll
cp 7zip-full/7z.exe 7zip-full/7z.dll /c/7zip/
export PATH="/c/7zip:$PATH"                # Python 的 shutil.which('7z') 即可命中
```

## 步骤 3：vendor/（四个来源，缺一不可）
```bash
PP_GXX='C:\mingw64\bin\g++.exe'
python tools/fetch_deps.py     # → vendor/sdl3（头文件+导入库+运行时 DLL）、vendor/ffmpeg
```
`fetch_deps.py` **两个已知缺陷**，必须手工补：
1. **SDL3 运行时不落地**：glob 写的是 `SDL3-win32-x64*`，实际解压目录是 `SDL3-3.4.16-win32-x64` → 不匹配，`vendor/sdl3/bin` 为空。
   手工拷贝**必须选 x64**：`_deps/extract/SDL3.dll`（devel 包里还带 i686 版，拷错会导致 dist 里混入 32 位 DLL）。用 PE Machine 字段核验（`0x8664`=x64，`0x14c`=i386）。
2. **FFmpeg 哈希钉值永不生效**：`DEPS_SHA256` 的键是 `ffmpeg-shared.7z`，而下载保存名是 `ffmpeg-9.0.1-full_build-shared.7z` → 只打印 WARN。内容是 TOFU 钉的那份（实测哈希与钉值一致），可把版本化文件名补进键名。

```bash
# stb：没有任何脚本提供，但 src/core/font.cpp 硬依赖
mkdir -p vendor/stb && curl -Lo vendor/stb/stb_truetype.h \
  https://raw.githubusercontent.com/nothings/stb/master/stb_truetype.h

# libass 字幕栈（subtitles 插件需要）
pip install zstandard                 # fetch_libass.py 唯一第三方依赖
python tools/fetch_libass.py          # → vendor/libass/bin（32 个 DLL，闭包已校验）
```
`fetch_libass.py` **只产出 bin/**，而 build.py 编译 `subtitles` 需要 `-Ivendor/libass/include` 与 `-Lvendor/libass/lib -lass`。
从它已下载的包里抽出来（否则 subtitles 编译失败）：
```python
# 包内路径：mingw64/include/ass/ass.h、ass_types.h、mingw64/lib/libass.dll.a
pkg = r"_deps\libass\mingw-w64-x86_64-libass-<ver>-any.pkg.tar.zst"
# zstandard 解 tar → 投放为 vendor/libass/{include\ass\,lib\}（白名单条目 + 拒绝 .. / 绝对路径）
```

## 步骤 4：构建
```bash
export PP_GXX='C:\mingw64\bin\g++.exe'     # build.py 默认 F:/mingw64/... 多半不存在
python build.py --release                   # 干净重建 + 插件清单 + 清运行期产物
```
成功口径：`[PASS] 构建成功`、`可发布文件 57 个，合计 144.2 MB`、11 个插件全编译。
（`--release` 隐含 `--clean`；不带它 dist/ 会累积日志与自检证据。）

## 步骤 4.5：改代码时怎么提交（**先确认这里有没有 `.git`**）

`C:\pluginplayer-main` 往往是**源码 zip 解包**出来的（目录里能看到
`pluginplayer-main.zip`，还套着一层同名的 `pluginplayer-main/`），**它不是一个 git 仓库** ——
在这里改完代码**推不了**。正确做法是「构建在解包树、提交在克隆」：

```bash
# 1) 克隆到仓库外的临时目录（工具链/vendor 都不动它）
git clone https://gitee.com/siwpan/pluginplayer.git /c/tmp/pp-prs/pluginplayer
cd /c/tmp/pp-prs/pluginplayer
git config user.name siwpan && git config user.email siwpan@users.noreply.gitee.com
git config http.version HTTP/1.1          # 见步骤 6 第 1 个坑

# 2) 只把**你改过的那些文件**拷进克隆（保留改前的 copy 作对照）
for f in src/core/app.cpp src/sdk/player_plugin.h README.md ...; do
  cp "/c/pluginplayer-main/$f" "$f"
done

# 3) 提交前先看 diffstat —— 应当**只有**你改的文件，且没有整文件级行尾噪声
git status --short && git diff --stat
```

- 若 `git diff --stat` 里冒出一堆你没碰过的文件、或某文件改动行数 ≈ 文件总行数，
  多半是**行尾被改写**（CRLF↔LF）。本仓库源码是 **LF**；用 `io.open(..., newline="")`
  之类的脚本整文件改写时要小心，读入时的通用换行会把 `\r\n` 折成 `\n`。
- 令牌只放仓库外（本机约定 `C:\tmp\pp-toolchain\.gitee_token`），**任何情况下不写进仓库**。

## 步骤 5：验证（两层）
```bash
python tools/verify.py       # 机械门禁 17~18 项
```
- `third-party-notices` 失败通常**与构建无关**：生成器读 `host-js/node_modules` 取 Cordis 版本，未 `npm install` 就写「未安装」→ 判定过期。差异可这样核对：`gen_third_party_notices.py --print` + `diff --strip-trailing-cr`（整文件 diff 全是行尾差异时，忽略 CR 才能看到真实改动）。
- 该生成器的 MinGW 版本串是**写死的常量**，换工具链后会与实物不符（如仍写 GCC 16.1.0 而实际 15.2.0）。

端到端无窗口自检（最强证据）：
```bash
cd dist
../vendor/ffmpeg/bin/ffmpeg.exe -y -loglevel error -f lavfi -i testsrc2=size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=440:sample_rate=48000 -t 8 -c:v libx264 -preset veryfast \
  -pix_fmt yuv420p -c:a aac -shortest test_assets/sample.mp4
./pluginplayer.exe --selftest --frames 90 --out selftest_out test_assets/sample.mp4
# 期望：==== 自检结束: 15/15 项通过 ====，退出码 0，11 个插件加载失败 0
```
自检会在 dist/ 里留下 `test_assets/`、`selftest_out/` 与 `config/rpc-token.txt`；
**重跑一次 `build.py --release`** 即可恢复干净的发布载荷（实测可复现：两次构建都是 57 文件 / 144.2 MB）。
反过来说：**`--release` 会清空 `dist/`，你刚生成的 `test_assets/*.mp4` 一并没了** ——
改完代码先构建、再生成媒体、再自检，顺序别反（否则会看到「无法打开媒体」而误判成构建坏了）。

### 自检到底几项：`15/15` 还是 `14/14 + 跳过 1`
一共 15 个步骤。「跳过 ≠ 失败」，两项最常见的不适用：

- **素材没有音频轨 → `track_switch` 跳过**（文案：`媒体没有音频轨，不适用多轨切换校验`）。
  所以 HDR 测试片（只 `-c:v`、没有 `-c:a`）自检结果是 **14/14，跳过 1 项**，这是正常的。
- 两项都要**看文案**才能区分「跳过了」和「跑失败」——别只比总数。
- 另外 `track_switch` 自己按设计**等 8 秒**（`dl = now + 8.0`）。所以「一整轮自检 3.7 s」
  与「12.5 s」的差别常常只是前者跳过了它，**不是**你的改动变慢了。

### 加一条 HDR 测试片（验 HDR 链路时必备）
仓库自带的样例是 SDR。要验 HDR（色彩空间 / 色调映射 / 输出重建），需要一条**带 BT.2020+PQ 标注**
的片子；标注会经容器 `colr` 进 `codecpar`，被内核读成 `primaries=9,trc=16`：

```bash
FF=vendor/ffmpeg/bin/ffmpeg.exe
$FF -y -loglevel error -f lavfi -i "testsrc2=size=1280x720:rate=30" -t 8 \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p \
  -color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc \
  -x264-params "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc" \
  dist/test_assets/hdr_pq.mp4
$FF -hide_banner -i dist/test_assets/hdr_pq.mp4 2>&1 | grep Video   # 核对标注真的写进去了
```

注意这是 **8-bit 包着 PQ 标注**的管子 —— 足够打通「元数据 → 判据 → 帧链 → 输出链路」，
但内容**不是**合法的 PQ 信号，不能用来判断色调映射的观感（那由单测的已知字节负责）。

### 只想看插件在真实播放路径下的行为？用控制通道，别指望自检
自检的 `decode_and_display` 循环**不发布 `app.tick`**（历史上因此漏掉过一个「HDR 元数据从未
写回帧、auto 恒不激活」的缺陷）。要验证 tick 驱动的插件（`video_tonemap`、`osd_stats`），
走正常播放 + RPC：

```bash
cd dist
./pluginplayer.exe --rpc-port 7911 test_assets/hdr_pq.mp4 > run.log 2>&1 &
sleep 4
python ../tools/pp_cli.py cmd tonemap.mode auto --port 7911    # 需要时显式开启
sleep 3
python ../tools/pp_cli.py status --port 7911                   # 看实测 fps / 丢帧
grep -E "色彩:|显示端|已挂帧处理器|不支持 HDR" run.log
```
插件状态命令的**输出走播放器自己的日志**（RPC 只回一个退出码），所以要看 `run.log`。

## 步骤 6：发布到 Gitee（可选）

工具 `tools/gitee_release.py`（幂等，中断可重跑）。令牌只走 `--token-file` / `GITEE_TOKEN`，
**绝不写进仓库**。

**打包口径别自己发明** —— 直接用仓库自己的 `gen_third_party_notices.dist_payload()`
（`gitee_release.py upload` 用的也是它，保持单一真相）：

```python
import sys; sys.path.insert(0, r"<repo>\tools")
import gen_third_party_notices as n
payload = n.dist_payload(dist=r"<repo>\dist")   # [(相对路径, 字节数)]
# 按 payload 逐个 write 进 zip，arcname=相对路径 → zip 根就是 dist 的内容
```

- **zip 根必须是 dist 的「内容」**，不能套一层 `dist/`：消费方是
  `zipfile.extractall(external/pluginplayer/dist)` 后直接找 `pluginplayer.exe`。
- 144.2 MB → zip 约 55.9 MB（2.58x），Gitee 单附件上限 100 MB。
- 顺手生成 `SHA256SUMS.txt`（`<hex>  <文件名>`），一起当附件传。
- 校验：`verify.py` 的 `release-payload` 门禁会核对文件数与 README 记录是否一致。

```bash
TAG=v1.2.0        # 换成本次要发的版本
python tools/gitee_release.py release --name pluginplayer --tag $TAG \
    --title "PluginPlayer $TAG" --branch main --notes-file release-notes.md
python tools/gitee_release.py attach --name pluginplayer --tag $TAG \
    --file pluginplayer-$TAG-win64.zip --file SHA256SUMS.txt
```

发版后**消费方不用改任何代码**（private-radio-stations 的 `fetch-deps.py` 每次运行都去
`/releases/latest` 解析 tag）。可以这样一条命令取证：

```bash
python -c "import importlib.util as u; s=u.spec_from_file_location('fd',r'C:\private-radio-stations-master\scripts\fetch-deps.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.resolve_pluginplayer())"
# 期望 tag == 刚发的那个；sums_url 里也能取到 SHA-256 用于对账
```

### 发布环节的 5 个实测坑（2026-09-14 全部撞过）

1. **`git push` 到 Gitee 报 `send-pack: unexpected disconnect while reading sideband packet`**
   —— HTTP/2 下推送被服务端断开、命令挂到超时（**只有 push 会，fetch/clone 正常**）。
   解法：`git config http.version HTTP/1.1`（或 `git -c http.version=HTTP/1.1 push`）。
   *这是最耗时的坑——现象像网络慢，实际是协议版本。*
2. **建发行版必须给 `target_commitish`**：不传时 `400 {'messages': ['target_commitish is missing']}`。
   `release` 子命令要加 `--branch main`。（DEPLOY.md 早先示例没带，照抄会失败。）
3. **附件上传路径必须带 `/api/v5` 前缀**：`upload_file()` 自己建 HTTPS 连接，
   不像 `api()` 会补前缀。漏前缀 → POST 到网页路由 → 返回 **404 HTML**，
   表现为「上传失败但看不出是路径问题」。修复见 `upload_attachments()` 的 `API_PREFIX`
   （2026-09-14 已提交修复 `79b5b25`）。
4. **`git tag -a` 要求仓库已配身份**：新克隆没 `user.name`/`user.email` 时以 128 失败
   （`unable to auto-detect email address`）。
5. **`release` 作用在「本地仓库」上**：`--repo` 默认取脚本所在仓库根。从别处调脚本时
   必须显式 `--repo <本地克隆路径>`，否则会在非 git 目录里跑 `git tag`。

### 发布后必做
**回下载附件比对 SHA-256**（别只看「上传成功」）：

```bash
curl -sL -o rd.zip "https://gitee.com/<owner>/<repo>/releases/download/<tag>/<附件名>"
sha256sum rd.zip   # 必须与本地原件一致
```

注意：接口返回的 `assets` 里会**多出 2 个 Gitee 自动附的源码包**（`<tag>.zip` / `.tar.gz`），
所以「附件 N 个」比实传数多 2 属正常。那两个链接**不是直链**（匿名 HTTP 拿到的是 HTML），
GPL 义务的源码指向要写 `git clone` 地址。

## 何时不该重新构建
消费方（private-radio-stations 等）只是路径指错时，**先修路径**，别急着重编译——
现成的 dist 往往本来就能跑（查它的历史日志有无「插件 N 个全部加载成功 / 认证通过」）。
