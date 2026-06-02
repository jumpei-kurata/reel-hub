# Reel Hub

Instagramの動画をダウンロードして、Facebookページ・Instagramに投稿するプライベートツール。

## 機能

- Instagram URLから動画をダウンロード → Facebookに投稿 & カメラロールに保存
- ローカル動画ファイルをアップロード → Facebook & Instagramに自動投稿
- キャプション・ハッシュタグ編集UI：4つの固定タグ事前入力 + 可変5つ目をチップタップで追加/削除
- コメント自動いいね（他人のコメント＋返信、2階層）＋ 絵文字オンリーコメントへの13パターン絵文字ランダム返信
- FBトークンを起床時に自動リフレッシュ（残25日未満で更新・人手介入不要。※現トークンは無期限型）
- IG投稿パフォーマンス確認用インサイトダッシュボード（タブ統合・ソート対応）

## 現在の状態

| 機能 | 状態 |
|------|------|
| Instagram URLダウンロード | ✅ 動作中 |
| Facebook自動投稿（URL/アップロード両対応） | ✅ 動作中 |
| カメラロール保存（iOS Web Share API） | ✅ 動作中 |
| Instagramへの自動投稿（アップロード時） | ⚠️ コード実装済み・H.264動画のみ対応（後述） |
| コメント自動いいね＆絵文字返信 | ✅ 稼働中（**GitHub Actions が3hごとに起こし起床時に実行**・Upstash 永続dedupで再いいね非破壊） |
| トークン自動リフレッシュ | ✅ 稼働中（**起床時に残日数チェック→25日未満で自動更新**。※現トークンは無期限のため実発火せず） |
| インサイトダッシュボード | ✅ 稼働中（`/` の「📊 インサイト」タブ） |
| ハッシュタグチップ | ✅ 投稿画面に5チップ実装済み |
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
| ホスティング | Render 無料枠（スリープ運用・常時起動しない。初回アクセスは~60秒のコールドスタート） |
| 定期起こし | **GitHub Actions**（`.github/workflows/reel-hub-wake.yml`）が3hごとに `/ping` で起こす。月~70h（750h上限内） |
| 自動保守 | 起床ごとに `main.py` lifespan がコメント処理＋トークンチェックを実行 |
| dedup（再いいね防止） | **Upstash Redis（無料枠）** に「いいね済みID」を永続保存。スリープで消えず toggle で外さない |
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

### スリープ運用 ＋ GitHub Actions 起こし役

本サービスは**あえて常時起動させない**。24時間 keep-alive すると Render 無料枠の月間インスタンス時間（750h/ワークスペース）をほぼ使い切りサスペンドを招くため、常時 keep-alive は**廃止**（2026-06。旧 cron-job.org の14分ping を停止）。

代わりに **GitHub Actions の起こし役**（`.github/workflows/reel-hub-wake.yml`）が**3時間ごとに `/ping` を叩いて起こす**（flaky な hibernate-wake をリトライで吸収）。起床（=コールドスタート）するたびに `main.py` の lifespan が自動保守（コメント処理＋トークンチェック）をバックグラウンド実行する。

- **ユーザーが開かなくても3hごとに回る**（無人運用）。新コメントは最大~3hで反映（リアルタイムではない）
- 1回の起床で~15-20分稼働 → 月**~70時間**（750h上限に余裕）
- 頻度を変えるなら `reel-hub-wake.yml` の cron を編集（`17 */3 * * *`＝3h毎 → `17 * * * *`＝1h毎 など）

> ⚠️ GitHub の定期ワークフローは**リポジトリに60日コミットが無いと自動停止**する（メール通知＋1クリック再開）。長期放置後に「自動いいねが止まった」場合は Actions タブで `reel-hub wake` を re-enable。

---

## 環境変数

Renderの Environment Variables に以下を設定する。

| Key | 説明 |
|-----|------|
| `APP_BASE_URL` | `https://reel-hub.onrender.com` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | 長期ユーザーアクセストークン（60日有効・自動リフレッシュ運用） |
| `FACEBOOK_PAGE_ID` | 投稿先 Facebook Page ID。動画投稿時に `/me/accounts` から Page トークンを引いて `/{page-id}/videos` を叩く |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | InstagramビジネスアカウントID（`17841400539477896` = Jumpei-Dance） |
| `FACEBOOK_APP_ID` | Meta AppのアプリID（自動リフレッシュ用） |
| `FACEBOOK_APP_SECRET` | Meta Appのアプリシークレット（自動リフレッシュ用） |
| `RENDER_API_KEY` | Render REST APIキー（自動リフレッシュ用） |
| `RENDER_SERVICE_ID` | Render Service ID（`srv-xxxxx`、自動リフレッシュ用） |
| `REFRESH_SECRET` | `/api/refresh-token` 認可用ランダム文字列（`openssl rand -hex 32`） |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis の REST URL（コメントいいね済みIDの永続dedup用。[upstash.com](https://upstash.com) 無料枠） |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis の REST トークン（同上。Read-Only ではなく書き込み可のトークン） |

> **Upstash セットアップ**: upstash.com → Create Database（Redis・Free・Eviction OFF）→ 「REST API」欄の上記2値を Render env に貼る。`/auth/status?secret={REFRESH_SECRET}` の `dedup_store: "ok"` で疎通確認。

---

## Instagram自動投稿セットアップ（✅ 完了済み）

> **セットアップ完了**。`INSTAGRAM_BUSINESS_ACCOUNT_ID=17841400539477896` がRenderに設定済み。
> 以下は手順の参考記録。

### 1. Meta AppにInstagram権限を追加

1. [developers.facebook.com](https://developers.facebook.com) → reel-hub → ユースケース
2. 「Instagramグラフ API」を追加
3. 権限に `instagram_content_publish`、`instagram_basic` を追加

> **注意**: アプリレビューが必要になる可能性あり。開発モードのままなら自分のアカウントにのみ投稿可能。

### 2. INSTAGRAM_BUSINESS_ACCOUNT_IDを取得

グラフAPIエクスプローラーで以下を実行（ユーザートークンが必要）：

```
GET /me/accounts?fields=name,instagram_business_account{id,username}
```

レスポンスの `instagram_business_account.id` の値をコピー。

### 3. Renderに環境変数を設定

`INSTAGRAM_BUSINESS_ACCOUNT_ID` に取得したIDを設定 → Redeploy。

---

## 投稿画面のキャプションUI

### デフォルトキャプション

```
\n\n#ダンス #ブレイクダンス #dance #breakdance 
```

末尾に半角スペース付き（次のタグを書き始めやすいように）。

### ハッシュタグチップ

textarea の下に並ぶチップボタンで、可変位置のハッシュタグをタップで追加/削除：

| チップ | 用途 |
|--------|------|
| `#powermoves` | パワームーブ系の動画 |
| `#training` | 練習風景 |
| `#workout` | ワークアウト・体作り系 |
| `#breakin` | ブレイキン全般 |
| `#bboy` | Bボーイング |

- **タップで追加** → 紫ハイライト
- **再タップで削除** → 文中の該当 `#tag` を削除
- **手動編集と同期** → textarea に直接書いてもチップ状態が反映される

### 追加方法

`app/static/index.html` の `<div class="chips" id="hashtag-chips">` 内に `<button class="chip" type="button" data-tag="newtag">#newtag</button>` を1行足すだけ。`data-tag` の値（`#` 抜き）がそのまま追加されるタグ名になる。

---

## コメント自動いいね＆絵文字返信（✅ 稼働中）

### 動作仕様

最新10件のIG投稿について、コメントとその返信（2階層）をスキャンして以下を実行：

| ケース | いいね | 絵文字返信 |
|--------|--------|-----------|
| 他人のトップコメント（テキスト） | ✅ | ❌ |
| 他人のトップコメント（絵文字のみ） | ✅ | ✅ `🔥🔥` `🔥❤️` `😎🔥` 等の2文字以上絵文字組合せから1個ランダム |
| 自分のトップコメント | ❌ | ❌ |
| 他人の返信（どんな内容でも） | ✅ | ❌ |
| 自分の返信 | ❌ | ❌ |

> Instagramのコメントは**2階層仕様**（トップコメント → リプライ）でリプライへのリプライは存在しないため、この2階層スキャンで全パターン網羅。

### 重複防止（再いいね toggle 対策）

- いいねは**同じコメントに2回POSTすると toggle で外れる**。だから「いいね済みID」を **Upstash Redis に永続保存**（`reel-hub:processed_comments` キー・**TTL無し**＝一度処理したら永久に記録）。起床のたびに再いいねして既存いいねを外す事故を防ぐ
- Render はスリープで `/tmp` が消えるが、Upstash は外部の永続ストアなので消えない（旧 `/tmp/processed_comments.json`＋TTL30日 方式は2026-06に Upstash・TTL無しへ移行。TTLがあると30日後に再いいね→toggleが復活するため撤廃）
- **Upstash が未設定 or 不通のときは、いいね自体を停止**（誤って既存いいねを外さない安全装置。`/auth/status?secret=` の `dedup_store` で疎通確認可）
- 絵文字返信は上記に加え `_already_replied` API チェック（返信POST時にAPI上の既存返信を確認）で二重返信も防止

### 必要な権限（Render env var `FACEBOOK_PAGE_ACCESS_TOKEN` のトークンに付与済み）

- `instagram_manage_comments`（コメント取得・返信POST）
- `instagram_manage_engagement`（いいねPOST用、新エンドポイント `POST /{ig-user-id}/likes?comment_id=...`）

> **ページトークンは仕様上 `/likes` で弾かれる**（scopeを持たせても認可されない、ユーザーidentityが必要なため）。
> 本番では**長期ユーザートークン（60日有効・起床時に自動リフレッシュ）**を使用。

### 実行タイミング

**GitHub Actions の起こし役**（`reel-hub-wake.yml`）が3hごとにサービスを起こし、起床ごとに `main.py` の lifespan が `process_comments()` をバックグラウンド実行する。**＝ユーザーが開かなくても3hごとに新コメントを処理**（最大~3時間で反映・リアルタイムではない）。`POST /api/instagram/process-comments` エンドポイントは手動/デバッグ用に残置。

> 処理済みIDは Upstash に永続保存（TTL無し）なので、起床のたびに再いいね→toggle で外す事故は起きない（上記「重複防止」）。

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

### UIダッシュボード

**メインページ https://reel-hub.onrender.com/ の「📊 インサイト」タブから利用**。

初回 `REFRESH_SECRET` を入力すると `localStorage` に保存され、以降タブを切り替えるだけで自動ロード。再生数/リーチ/いいね/コメント/保存/シェア/新着 でソート切替可能。各カードからInstagram投稿へワンタップ遷移。

### エンドポイント（curl版）

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

## Facebookアクセストークンの取得（初回のみ）

> **背景**: 本番では**長期ユーザートークン（60日有効）**を `FACEBOOK_PAGE_ACCESS_TOKEN` に保存。
> 60日切れは次セクションの**自動リフレッシュ**（起床時に自動）で更新するため、初回1回だけ手動で取得が必要。
>
> ※ かつてページトークン（無期限）を使っていたが、コメントいいねの新エンドポイント
> `POST /{ig-user-id}/likes` がページトークンでは認可されないため、ユーザートークン経路に移行。

### 1. Meta Developer でアプリ準備

1. [developers.facebook.com](https://developers.facebook.com) → マイアプリ → アプリを作成（既存ならスキップ）
2. **ユースケース → カスタマイズ** で以下のスコープを追加：
   - Page Management: `business_management`, `pages_manage_engagement`, `pages_manage_metadata`, `pages_manage_posts`, `pages_read_engagement`, `pages_read_user_content`, `pages_show_list`, `read_insights`
   - Instagram API: `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_engagement`, `instagram_manage_insights`, `instagram_manage_messages`

### 2. 短命ユーザートークンを生成

1. **ツール → グラフAPIエクスプローラー**
2. Metaアプリ: `reel-hub` を選択
3. **User or Page** → `ユーザートークン`
4. アクセス許可：①で追加した全スコープにチェック
5. **Generate Access Token** → Facebookログイン・全許可
6. 生成されたトークンをコピー（これは1時間で失効する短命トークン）

### 3. 長期トークンに交換（60日有効）

ブラウザで以下のURLにアクセス（値を置き換えて）：

```
https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={アプリID}
  &client_secret={アプリシークレット}
  &fb_exchange_token={短命トークン}
```

レスポンスの `access_token` が**長期ユーザートークン**（60日有効）。

### 4. Page IDを取得

ブラウザで以下にアクセスして、投稿先 Facebook Page の `id` を控える（値を置き換え）：

```
https://graph.facebook.com/v19.0/me/accounts?fields=id,name&access_token={長期ユーザートークン}
```

レスポンス `data[].id` が **Facebook Page ID**。投稿したい Page の id を控える。

### 5. Renderに設定

以下を Render の Environment Variables に設定 → 自動 Redeploy：

- `FACEBOOK_PAGE_ACCESS_TOKEN` ← 長期ユーザートークン
- `FACEBOOK_PAGE_ID` ← 上で取得した Page ID

以降は次セクションの**自動リフレッシュ**（起床時に自動）が動くため、手動更新は不要。

---

## トークン自動リフレッシュ

長期ユーザートークンは60日で失効する。**起床時の自動保守**がこれを自動更新するため、手動運用も専用の更新cronも不要（GitHub Actions 起こし役の起床に相乗りで走る）。

> **※ 現在の本番トークンは無期限型**（`debug_token` の `expires_at=0`。`/auth/status?secret={REFRESH_SECRET}` で確認可）。そのため実際には更新は発火しない（そもそも切れない）。下記の仕組みは**将来60日型トークンに差し替えた場合の安全網**として残してある。

### 仕組み

```
GitHub Actions が3hごとに /ping で起こす（=起床）
  → main.py lifespan が auto_maintenance.run_wake_maintenance() を実行
  → debug_token で残日数を確認
  → 残り <25日 のときだけ refresh_facebook_token():
      → fb_exchange_token で新60日トークンを取得
      → Render API で FACEBOOK_PAGE_ACCESS_TOKEN env var を書き換え
      → Renderが自動再デプロイ（新トークンで起動）
```

毎日アクセスする限りトークンは永久に切れない。更新は実質~35日に1回（=再デプロイ1回）で済む。残日数は `/auth/status` の `token_days_remaining` で確認できる。

### 必要な環境変数

| Key | 取得方法 |
|-----|----------|
| `FACEBOOK_APP_ID` | Meta App Dashboard → 設定 → ベーシック |
| `FACEBOOK_APP_SECRET` | 同上の「表示」ボタン |
| `RENDER_API_KEY` | Render Dashboard → Account Settings → API Keys |
| `RENDER_SERVICE_ID` | Render Dashboard サービスURL末尾の `srv-xxxxx` |
| `REFRESH_SECRET` | `openssl rand -hex 32` で生成した任意文字列 |

### 専用の更新cronは廃止（起床時に自動）

旧構成では cron-job.org で月1 POST していたが、スリープ運用への移行で**廃止**。更新は GitHub Actions 起こし役による起床時の自動保守が担う。`POST /api/refresh-token?secret=...` は手動更新用に残置（下記「手動実行」）。

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

## TikTok セットアップ（❌ 廃止・歴史的記録）

> **TikTok統合は廃止しました**（コミット `3292bb6` で削除）。Sandbox外で公開できない制約 + ポリシー違反通知のため。
> 以下は過去に試したセットアップ手順の保存。再挑戦する人向けの参考情報。

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
