# Reel Hub

Instagramの動画をダウンロードして、TikTok・Facebookページに投稿するプライベートツール。

## 機能

- Instagram URLから動画をダウンロード
- iPhoneカメラロールへ保存
- Facebookページへ即時投稿 / 下書き保存
- TikTokへ投稿
- キャプション・ハッシュタグを毎回編集可能

## 技術構成

| 項目 | 内容 |
|------|------|
| バックエンド | FastAPI + Python |
| 動画DL | yt-dlp |
| ホスティング | Render 無料枠 |
| スリープ対策 | cron-job.org（14分おきに /ping） |
| フロントエンド | バニラ HTML/CSS/JS（iPhone Safari対応） |

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
| `TIKTOK_CLIENT_KEY` | TikTok Developer AppのClient Key |
| `TIKTOK_CLIENT_SECRET` | TikTok Developer AppのClient Secret |
| `TIKTOK_ACCESS_TOKEN` | `/auth/tiktok` で認証後に取得 |
| `TIKTOK_REFRESH_TOKEN` | 同上 |

---

## Facebook ページアクセストークンの取得

> **ポイント**: Graph APIエクスプローラーで生成したトークンは約1時間で失効する。
> 長期トークン経由でページトークンを取得すると**無期限**になる。

### 1. Meta Developerでアプリ作成

1. [developers.facebook.com](https://developers.facebook.com) → マイアプリ → アプリを作成
2. 「ユースケースなしでアプリを作成」を選択
3. アプリ作成後、**ユースケース → カスタマイズ** から以下を追加：
   - `pages_manage_posts`
   - `pages_show_list`

### 2. 短命ユーザートークンを生成

1. **ツール → グラフAPIエクスプローラー**
2. Metaアプリ: `reel-hub` を選択
3. アクセス許可に `pages_manage_posts`、`pages_show_list` を追加
4. **「Generate Access Token」** を押してFacebookでログイン・許可
5. 生成されたトークンをコピー（これは短命トークン）

### 3. 長期トークンに交換（60日→ページトークンは無期限）

アプリIDとアプリシークレットを確認する：
- アプリID: マイアプリのダッシュボードに表示
- アプリシークレット: アプリの設定 → ベーシック → アプリシークレット

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

### 5. Renderに設定

`FACEBOOK_PAGE_ACCESS_TOKEN` に無期限トークンを設定してRedeploy。

---

## TikTok セットアップ

### 1. Developer登録

1. [developers.tiktok.com](https://developers.tiktok.com) でアプリ作成（無料）
2. Content Posting APIのアクセス申請（審査に数日かかる）
3. 承認後、Client Key と Client Secret を取得
4. Renderの環境変数に `TIKTOK_CLIENT_KEY`、`TIKTOK_CLIENT_SECRET` を設定

### 2. 認証

デプロイ済みのアプリで `https://reel-hub.onrender.com/auth/tiktok` にアクセス。
TikTokでログイン・許可すると、画面にトークンが表示される。
それを `TIKTOK_ACCESS_TOKEN`、`TIKTOK_REFRESH_TOKEN` に設定してRedeploy。

> **注意**: TikTokアクセストークンは24時間で失効する。
> 毎日使う場合は `/auth/tiktok` で再認証が必要。

---

## 注意事項

- Renderの無料枠は**永続保証なし**（現時点で750時間/月）
- yt-dlpはInstagramの公開投稿のみ対応（非公開投稿はクッキー認証が別途必要）
- このツールは自分のコンテンツの再投稿を目的としたプライベート利用のみ
