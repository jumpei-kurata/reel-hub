# Reel Hub

Instagramの動画をダウンロードして、Facebookページ・Instagramに投稿するプライベートツール。

## 機能

- Instagram URLから動画をダウンロード → Facebookに投稿 & カメラロールに保存
- ローカル動画ファイルをアップロード → Facebook & Instagramに自動投稿
- キャプション・ハッシュタグを毎回編集可能（デフォルト: `#ダンス #ブレイクダンス #dance #breakdance #`）

## 現在の状態（2026-05-02）

| 機能 | 状態 |
|------|------|
| Instagram URLダウンロード | ✅ 動作中 |
| Facebook自動投稿 | ✅ 動作中 |
| カメラロール保存（iOS Web Share API） | ✅ 動作中 |
| Instagramへの自動投稿 | ⚠️ コード実装済み・Meta Portal設定待ち（後日作業） |
| コメント自動いいね＆絵文字返信 | ⚠️ コード実装済み・cron-job.org設定待ち（Insta投稿確認後） |
| TikTok投稿 | ❌ 廃止（ポリシー違反・Sandbox非公開制限のため） |

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
| `FACEBOOK_PAGE_ACCESS_TOKEN` | 無期限ページアクセストークン（取得方法は後述） |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | InstagramビジネスアカウントID（取得方法は後述・**未設定**） |

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

## コメント自動いいね＆絵文字返信（⚠️ コード実装済み・Insta投稿確認後にcron設定）

> **無料で実装可能**。追加費用なし。

### 仕様

- 最新10件の投稿のコメントを全取得
- 全コメントに自動いいね
- 絵文字のみのコメント（アルファベット・数字・CJK文字を含まない）には `🔥🔥🔥` で自動返信
- 処理済みコメントIDは `/tmp/reel-hub/processed_comments.json` に保存（Render再起動で消えるが実害なし）

### 追加で必要な権限

- `instagram_business_manage_comments`（いいね・返信・コメント取得すべてこれ1つ）

### cron-job.org設定（Insta投稿が動いたら）

1. [cron-job.org](https://cron-job.org) でジョブを追加
2. URL: `https://reel-hub.onrender.com/api/instagram/process-comments`
3. Method: POST
4. Crontab: `*/7 * * * *`（7分ごと）

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
