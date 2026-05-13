# Reel Hub

Instagramの動画をダウンロードして、Facebookページ・Instagramに投稿するプライベートツール。

## 機能

- Instagram URLから動画をダウンロード → Facebookに投稿 & カメラロールに保存
- ローカル動画ファイルをアップロード → Facebook & Instagramに自動投稿
- キャプション・ハッシュタグを毎回編集可能（デフォルト: `#ダンス #ブレイクダンス #dance #breakdance #`）

## 現在の状態（2026-05-03）

| 機能 | 状態 |
|------|------|
| Instagram URLダウンロード | ✅ 動作中 |
| Facebook自動投稿（URL/アップロード両対応） | ✅ 動作中 |
| カメラロール保存（iOS Web Share API） | ✅ 動作中 |
| Instagramへの自動投稿（アップロード時） | ⚠️ コード実装済み・H.264動画のみ対応（後述） |
| コメント自動いいね＆絵文字返信 | ✅ 稼働中（長期ユーザートークン+月1自動リフレッシュ運用） |
| TikTok投稿 | ❌ 廃止（ポリシー違反・Sandbox非公開制限のため） |

### アップロード機能の既知の問題と経緯

**問題**: iPhoneのデフォルト録画フォーマット（HEVC/H.265）はInstagram Graph APIが拒否する（エラーコード2207076）。H.264のみ対応。

**試みたこと**:
- サーバー側でffmpegによる自動変換（imageio-ffmpeg）を実装したが、Render無料枠の512MBメモリ制限に抵触してOOMクラッシュ（117MBの動画でも発生）
- ffmpegの設定を軽量化（ultrafast, threads=1, refs=1）しても効果なし
- 根本原因: Pythonプロセスのfork+ffmpegサブプロセスの合計が512MBを超える

**現状の回避策**:
- iPhoneの設定 → カメラ → フォーマット → **Most Compatible** に変更するとH.264で録画される
- すでに録画済みのHEVC動画は、Photos → 共有 → Most Compatible でエクスポートしてからアップロード
- Renderのプランをアップグレード（Starter $7/月 = 2GBメモリ）すれば自動変換が動く

**なぜアップロード機能自体を残したか**:
- TikTokへの同時投稿ができれば価値があったが廃止になった
- 現状はネイティブアプリで直接投稿する方が手軽
- コード削除のコストが惜しいので機能は残置

## 技術構成

| 項目 | 内容 |
|------|------|
| バックエンド | FastAPI + Python |
| 動画DL | yt-dlp |
| ホスティング | Render 無料枠 |
| スリープ対策 | cron-job.org（14分おきに /ping） |
| フロントエンド | バニラ HTML/CSS/JS（iPhone Safari対応） |
| 認証ページ | GitHub Pages（docs/フォルダ） |

---

## セットアップ

### ローカル起動

```bash
uv sync
uv run uvicorn main:app --reload
# → http://localhost:8000
```

### Renderデプロイ

1. [render.com](https://render.com) でGitHub連携
2. New → Web Service → このリポジトリを選択
3. 設定：
   - **Build Command**: `uv sync --frozen && uv cache prune --ci`
   - **Start Command**: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables を設定（後述）
5. Deploy

### keep-alive（Renderのスリープ対策）

[cron-job.org](https://cron-job.org) で無料アカウントを作成し、以下を設定：
- URL: `https://reel-hub.onrender.com/ping`
- Crontab: `*/14 * * * *`（14分ごと）

---

## 環境変数

Renderの Environment Variables に以下を設定する。

| Key | 説明 |
|-----|------|
| `APP_BASE_URL` | `https://reel-hub.onrender.com` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | 長期ユーザーアクセストークン（60日有効・自動リフレッシュ運用） |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | InstagramビジネスアカウントID（取得方法は後述・**未設定**） |
| `FACEBOOK_APP_ID` | Meta AppのアプリID（自動リフレッシュ用） |
| `FACEBOOK_APP_SECRET` | Meta Appのアプリシークレット（自動リフレッシュ用） |
| `RENDER_API_KEY` | Render REST APIキー（自動リフレッシュ用） |
| `RENDER_SERVICE_ID` | Render Service ID（`srv-xxxxx`、自動リフレッシュ用） |
| `REFRESH_SECRET` | `/api/refresh-token` 認可用ランダム文字列（`openssl rand -hex 32`） |

---

## Instagram自動投稿セットアップ（⚠️ 後日作業）

> コードは実装済み。以下の手順を完了すれば動作する。

### 作業ステータス

- [x] バックエンド実装（`app/services/instagram.py`, `app/routes/instagram.py`）
- [x] フロントエンド実装（アップロード時のみ自動投稿ボタンに切り替わる）
- [ ] Meta AppにInstagram権限を追加
- [ ] InstagramビジネスアカウントIDを取得してRenderに設定

### 1. Meta AppにInstagram権限を追加

1. [developers.facebook.com](https://developers.facebook.com) → reel-hub → ユースケース
2. 「Instagramグラフ API」を追加
3. 権限に `instagram_content_publish`、`instagram_basic` を追加

> **注意**: アプリレビューが必要になる可能性あり。開発モードのままなら自分のアカウントにのみ投稿可能。

### 2. INSTAGRAM_BUSINESS_ACCOUNT_IDを取得

グラフAPIエクスプローラーで以下を実行（`FACEBOOK_PAGE_ACCESS_TOKEN`が必要）：

```
GET /{facebook_page_id}?fields=instagram_business_account&access_token={token}
```

レスポンスの `instagram_business_account.id` の値をコピー。

### 3. Renderに環境変数を設定

`INSTAGRAM_BUSINESS_ACCOUNT_ID` に取得したIDを設定 → Redeploy。

---

## コメント自動いいね＆絵文字返信（✅ 稼働中）

### 動作仕様

最新10件のIG投稿について、コメントとその返信（2階層）をスキャンして以下を実行：

| ケース | いいね | 絵文字返信 |
|--------|--------|-----------|
| 他人のトップコメント（テキスト） | ✅ | ❌ |
| 他人のトップコメント（絵文字のみ） | ✅ | ✅ `🔥` `😎` `👏` 等から1個ランダム |
| 自分のトップコメント | ❌ | ❌ |
| 他人の返信（どんな内容でも） | ✅ | ❌ |
| 自分の返信 | ❌ | ❌ |

> Instagramのコメントは**2階層仕様**（トップコメント → リプライ）でリプライへのリプライは存在しないため、この2階層スキャンで全パターン網羅。

### 重複防止

- 処理済みID（コメント・返信どちらも）は `/tmp/reel-hub/processed_comments.json` にTTL30日のdictで保存
- Render再起動で `/tmp/` が消えるが、`_already_replied` API チェック（返信POST時にAPI上の既存返信を確認）で重複返信は防止
- いいねは2回POSTすると toggle で外れるが、`processed` セットでガード

### 必要な権限（Render env var `FACEBOOK_PAGE_ACCESS_TOKEN` のトークンに付与済み）

- `instagram_manage_comments`（コメント取得・返信POST）
- `instagram_manage_engagement`（いいねPOST用、新エンドポイント `POST /{ig-user-id}/likes?comment_id=...`）

> **ページトークンは仕様上 `/likes` で弾かれる**（scopeを持たせても認可されない、ユーザーidentityが必要なため）。
> 本番では**長期ユーザートークン（60日有効・月1自動リフレッシュ）**を使用。

### cron-job.org設定（✅ 設定済み）

- Job: `reel-hub-process-comments`
- URL: `POST https://reel-hub.onrender.com/api/instagram/process-comments`
- 間隔: cron-job.org ダッシュボードで確認（README案では `*/7 * * * *` = 7分ごと）

### 手動実行

```bash
# 通常実行（processedキャッシュを尊重）
curl -X POST 'https://reel-hub.onrender.com/api/instagram/process-comments'

# 全コメント再処理（processedキャッシュ無視）
curl -X POST 'https://reel-hub.onrender.com/api/instagram/process-comments?reset=true'
```

---

## インサイト（投稿パフォーマンス確認）

最新N件のIG投稿のリーチ・保存・いいね・コメント・シェア・再生数を取得して、再生数順に並べる。

### エンドポイント

```bash
# デフォルト10件
curl 'https://reel-hub.onrender.com/api/insights?secret={REFRESH_SECRET}'

# 件数指定（1-25）
curl 'https://reel-hub.onrender.com/api/insights?secret={REFRESH_SECRET}&limit=25'
```

### レスポンス例

```json
{
  "count": 10,
  "media": [
    {
      "id": "18068301401560329",
      "type": "REELS",
      "timestamp": "2026-05-10T12:34:56+0000",
      "permalink": "https://www.instagram.com/p/...",
      "caption": "新作リール！",
      "insights": {
        "reach": 12345,
        "saved": 67,
        "likes": 890,
        "comments": 12,
        "shares": 34,
        "views": 54321
      }
    },
    ...
  ]
}
```

> **認可**: `REFRESH_SECRET` を `?secret=` に渡す（リフレッシュエンドポイントと同じ）

---

## Facebook ページアクセストークンの取得

> **ポイント**: Graph APIエクスプローラーで生成したトークンは約1時間で失効する。
> 長期トークン経由でページトークンを取得すると**無期限**になる。

### 1. Meta Developerでアプリ作成

1. [developers.facebook.com](https://developers.facebook.com) → マイアプリ → アプリを作成
2. 「ユースケースなしでアプリを作成」を選択
3. アプリ作成後、**ユースケース → カスタマイズ** から以下を追加：
   - `pages_read_engagement`（先に追加）
   - `pages_manage_posts`（後に追加）

> **注意**: `pages_manage_posts` を追加すると `pages_read_engagement` が依存関係として必要になる。必ず `pages_read_engagement` を先に追加すること。

### 2. 短命ユーザートークンを生成

1. **ツール → グラフAPIエクスプローラー**
2. Metaアプリ: `reel-hub` を選択
3. アクセス許可に `pages_manage_posts`、`pages_show_list` を追加
4. **「Generate Access Token」** を押してFacebookでログイン・許可
5. 生成されたトークンをコピー（これは短命トークン）

> **注意**: Graph APIエクスプローラーは個人プロフィールではなくページに切り替えてから操作すること。

### 3. 長期トークンに交換（60日→ページトークンは無期限）

ブラウザで以下のURLにアクセス（値を置き換えて）：

```
https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={アプリID}
  &client_secret={アプリシークレット}
  &fb_exchange_token={短命トークン}
```

レスポンスの `access_token` が長期ユーザートークン。

### 4. 無期限ページアクセストークンを取得

グラフAPIエクスプローラーのアクセストークン欄に長期ユーザートークンを貼り付けて、
URLを `me/accounts` にして送信。

レスポンスのページ一覧から自分のページの `access_token` をコピー。
**これが無期限のページアクセストークン。**

> **補足**: `me/accounts` を叩くたびにトークンが変わるように見えるが、同じトークンが返ってくるのが正常。毎回コピーし直す必要はない。

### 5. Renderに設定

`FACEBOOK_PAGE_ACCESS_TOKEN` に無期限トークンを設定してRedeploy。

> **重要**: コメントいいね機能（`POST /{ig-user-id}/likes`）は**ページトークンでは動かない**ため、reel-hub
> 本番では**長期ユーザートークン（60日有効）**を `FACEBOOK_PAGE_ACCESS_TOKEN` に入れる運用になっている。
> 60日切れ防止のため次セクションの**自動リフレッシュ**を必ず設定すること。

---

## トークン自動リフレッシュ

長期ユーザートークンは60日で失効する。これを月1回自動更新するエンドポイントとcronを用意してある。

### 仕組み

```
cron-job.org（月1回POST）
  → POST /api/refresh-token?secret=XXX
  → fb_exchange_token で新60日トークンを取得
  → Render API で FACEBOOK_PAGE_ACCESS_TOKEN env var を書き換え
  → Renderが自動再デプロイ
```

### 必要な環境変数

| Key | 取得方法 |
|-----|----------|
| `FACEBOOK_APP_ID` | Meta App Dashboard → 設定 → ベーシック |
| `FACEBOOK_APP_SECRET` | 同上の「表示」ボタン |
| `RENDER_API_KEY` | Render Dashboard → Account Settings → API Keys |
| `RENDER_SERVICE_ID` | Render Dashboard サービスURL末尾の `srv-xxxxx` |
| `REFRESH_SECRET` | `openssl rand -hex 32` で生成した任意文字列 |

### cron-job.org 設定

1. [cron-job.org](https://cron-job.org) でジョブ追加
2. URL: `https://reel-hub.onrender.com/api/refresh-token?secret={REFRESH_SECRET}`
3. Method: POST
4. Crontab: `0 3 1 * *`（毎月1日 03:00）

### 手動実行

```bash
curl -X POST "https://reel-hub.onrender.com/api/refresh-token?secret={REFRESH_SECRET}"
# → {"refreshed": true, "expires_in_seconds": 5183944}
```

### 失敗時の対処

レスポンスが `{"detail": "..."}` で500エラーなら：
- `missing env vars: ...` → 必要なenv varが未設定
- `fb_exchange_token: HTTP 4xx ...` → 現トークンが既に失効してる → 手動でExplorerから取り直してRender env varに貼り直し
- `render api: HTTP 4xx ...` → `RENDER_API_KEY` か `RENDER_SERVICE_ID` の値が違う

---

## TikTok セットアップ

> **現状（2026年5月時点）**: App Reviewに申請済み。審査通過後に本番利用可能になる。
> 審査中はSandbox環境でのみテスト可能。

### 1. Developer登録・アプリ作成

1. [developers.tiktok.com](https://developers.tiktok.com) でアプリ作成（無料）
2. **Login Kit** と **Content Posting API**（Direct Post ON）を追加
3. Scopes: `user.info.basic`, `video.publish`, `video.upload`

### 2. URLの認証（重要）

TikTok Developer PortalはURLの所有権確認が必要。RenderのドメインはCloudflare経由のため認証できないので、**GitHub Pagesを使う**。

1. このリポジトリのSettings → Pages → Branch: `main` / Folder: `/docs` で有効化
2. `https://jumpei-kurata.github.io/reel-hub/` がTikTokのToS URL・Privacy Policy URL・Web/Desktop URLになる
3. TikTokのVerify URL properties → URL prefix → `https://jumpei-kurata.github.io/reel-hub/` を入力
4. TikTokが提供する認証ファイル（`tiktokXXX.txt`）を `docs/` フォルダに配置してpush
5. GitHub Pagesの反映を待ってからVerify

### 3. Redirect URIの設定

Login Kit → Redirect URIs に追加：
```
https://reel-hub.onrender.com/auth/tiktok/callback
```
※ TikTokはhttps必須。localhostは不可。

### 4. App Review提出

- App Review用の説明文とデモ動画（mp4、50MB以内）が必要
- デモ動画: アプリのUI → Instagram動画DL → `/auth/tiktok` でOAuth → 投稿ボタンの流れを録画
- 審査には数日〜数週間かかる場合がある

### 5. Sandbox（審査中のテスト）

審査通過前はSandboxで動作確認できる。

1. Developer Portal → アプリ → Sandbox タブ → Sandbox作成
2. Sandbox → Sandbox settings → Test accounts → 自分のTikTokアカウントを追加
3. Sandbox → Products → Content Posting API を追加
4. Sandbox → Scopes → `video.publish`, `video.upload` を追加
5. Sandbox の Client Key・Secret を Render の環境変数に設定

### 6. 認証（トークン取得）

デプロイ済みのアプリで `https://reel-hub.onrender.com/auth/tiktok` にアクセス。
TikTokでログイン・許可すると、画面にトークンが表示される。
それを `TIKTOK_ACCESS_TOKEN`、`TIKTOK_REFRESH_TOKEN` に設定してRedeploy。

> **注意**: TikTokアクセストークンは24時間で失効する。
> 毎日使う場合は `/auth/tiktok` で再認証が必要。

---

## GitHub Pages（認証ファイル置き場）

`docs/` フォルダがGitHub Pages（`https://jumpei-kurata.github.io/reel-hub/`）として公開されている。
TikTokのURL認証ファイルや利用規約・プライバシーポリシーのページが含まれる。

| URL | 内容 |
|-----|------|
| `/terms.html` | 利用規約 |
| `/privacy.html` | プライバシーポリシー |
| `/tiktokXXX.txt` | TikTok URL認証ファイル |

---

## 注意事項

- Renderの無料枠は**永続保証なし**（現時点で750時間/月）
- yt-dlpはInstagramの公開投稿のみ対応（非公開投稿はクッキー認証が別途必要）
- このツールは自分のコンテンツの再投稿を目的としたプライベート利用のみ
- GitHubリポジトリはPublic（`.env` はgitignore済みなので認証情報は含まれない）
