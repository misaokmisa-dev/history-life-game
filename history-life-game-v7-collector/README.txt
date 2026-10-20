人生の続き v0.7 — 3,000人実データ収集セット

重要: people.json は未収録。未取得データを取得済みと偽りません。

方法A: 公開GitHubリポジトリにZIPの中身をアップロードし、Actions > Collect real Wikimedia biographies > Run workflow。成功したらActionsのartifact (history-life-data-and-site) から実データ付きのファイル一式を入手できます。
方法B: ネット接続したPCで環境変数WIKIMEDIA_CONTACTに有効な連絡先を指定し、python build_people_v7.py --limit 3000 --output people.json を実行します。

注意: Wikimediaのアクセス制限、検索負荷、実データ数・各人物の経歴量により3,000人に到達しない可能性があります。GitHub Actionsは1回の最大実行時間などの制限があるため、実行成功を保証しません。
人物の年齢は生年との差分で計算するため±1歳のズレがあります。日本語Wikipediaの文章に含まれる他人の行動を誤って本人の経歴と判定する可能性があります。文字列マッチングであり生成AIによる意味解釈ではありません。
各テキストの著作権ライセンスと帰属表示への対応が必要です。公開前に収録記録のレビューを推奨します。
