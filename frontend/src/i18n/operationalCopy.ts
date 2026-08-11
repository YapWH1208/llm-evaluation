import { Locale, localeIds } from "./catalog";

/**
 * Static vocabulary used by operational forms, tables, and controls.  Values
 * are ordered as zh-CN, fr, de, ru, ja, ko, and ms; English uses the source
 * token directly. Dynamic provider and user values never enter this map.
 */
const words: Record<string, readonly string[]> = {
  accept: ["接受", "accepter", "akzeptieren", "принять", "承諾", "수락", "terima"],
  accuracy: ["准确率", "précision", "Genauigkeit", "точность", "精度", "정확도", "ketepatan"],
  active: ["活动", "actif", "aktiv", "активный", "アクティブ", "활성", "aktif"],
  add: ["添加", "ajouter", "hinzufügen", "добавить", "追加", "추가", "tambah"],
  administrator: ["管理员", "administrateur", "Administrator", "администратор", "管理者", "관리자", "pentadbir"],
  after: ["之后", "après", "nach", "после", "後", "후", "selepas"],
  all: ["全部", "tous", "alle", "все", "すべて", "전체", "semua"],
  allow: ["允许", "autoriser", "erlauben", "разрешить", "許可", "허용", "benarkan"],
  analysis: ["分析", "analyse", "Analyse", "анализ", "分析", "분석", "analisis"],
  and: ["和", "et", "und", "и", "と", "및", "dan"],
  any: ["任何", "tout", "beliebig", "любой", "任意", "모든", "mana-mana"],
  application: ["应用", "application", "Anwendung", "приложение", "アプリケーション", "애플리케이션", "aplikasi"],
  archive: ["归档", "archiver", "archivieren", "архивировать", "アーカイブ", "보관", "arkib"],
  asset: ["资源", "ressource", "Asset", "ресурс", "アセット", "자산", "aset"],
  attempts: ["尝试", "tentatives", "Versuche", "попытки", "試行", "시도", "percubaan"],
  audit: ["审计", "audit", "Prüfung", "аудит", "監査", "감사", "audit"],
  available: ["可用", "disponible", "verfügbar", "доступный", "利用可能", "사용 가능", "tersedia"],
  baseline: ["基线", "référence", "Basislinie", "базовый", "ベースライン", "기준선", "garis asas"],
  benchmark: ["基准", "référentiel", "Benchmark", "бенчмарк", "ベンチマーク", "벤치마크", "penanda aras"],
  body: ["正文", "corps", "Textkörper", "тело", "本文", "본문", "badan"],
  browser: ["浏览器", "navigateur", "Browser", "браузер", "ブラウザ", "브라우저", "pelayar"],
  cache: ["缓存", "cache", "Cache", "кэш", "キャッシュ", "캐시", "cache"],
  cancel: ["取消", "annuler", "abbrechen", "отменить", "キャンセル", "취소", "batal"],
  cancelled: ["已取消", "annulée", "abgebrochen", "отменён", "キャンセル済み", "취소됨", "dibatalkan"],
  capability: ["能力", "capacité", "Fähigkeit", "возможность", "機能", "기능", "keupayaan"],
  cap: ["上限", "plafond", "Obergrenze", "лимит", "上限", "한도", "had"],
  catalog: ["目录", "catalogue", "Katalog", "каталог", "カタログ", "카탈로그", "katalog"],
  change: ["更改", "modifier", "ändern", "изменить", "変更", "변경", "ubah"],
  chart: ["图表", "graphique", "Diagramm", "диаграмма", "グラフ", "차트", "carta"],
  check: ["检查", "vérifier", "prüfen", "проверить", "確認", "확인", "semak"],
  choose: ["选择", "choisir", "auswählen", "выбрать", "選択", "선택", "pilih"],
  clear: ["清除", "effacer", "leeren", "очистить", "消去", "지우기", "kosongkan"],
  clone: ["克隆", "cloner", "klonen", "клонировать", "複製", "복제", "klon"],
  column: ["列", "colonne", "Spalte", "столбец", "列", "열", "lajur"],
  compare: ["比较", "comparer", "vergleichen", "сравнить", "比較", "비교", "bandingkan"],
  comparison: ["比较", "comparaison", "Vergleich", "сравнение", "比較", "비교", "perbandingan"],
  complete: ["完成", "terminé", "abgeschlossen", "завершён", "完了", "완료", "selesai"],
  completed: ["已完成", "terminé", "abgeschlossen", "завершено", "完了", "완료됨", "selesai"],
  configuration: ["配置", "configuration", "Konfiguration", "конфигурация", "設定", "구성", "konfigurasi"],
  configured: ["已配置", "configuré", "konfiguriert", "настроен", "設定済み", "구성됨", "dikonfigurasikan"],
  configure: ["配置", "configurer", "konfigurieren", "настроить", "設定", "구성", "konfigurasi"],
  connection: ["连接", "connexion", "Verbindung", "подключение", "接続", "연결", "sambungan"],
  content: ["内容", "contenu", "Inhalt", "содержимое", "コンテンツ", "콘텐츠", "kandungan"],
  cost: ["成本", "coût", "Kosten", "стоимость", "コスト", "비용", "kos"],
  context: ["上下文", "contexte", "Kontext", "контекст", "コンテキスト", "컨텍스트", "konteks"],
  create: ["创建", "créer", "erstellen", "создать", "作成", "생성", "cipta"],
  created: ["已创建", "créé", "erstellt", "создан", "作成済み", "생성됨", "dicipta"],
  current: ["当前", "actuel", "aktuell", "текущий", "現在", "현재", "semasa"],
  custom: ["自定义", "personnalisé", "benutzerdefiniert", "пользовательский", "カスタム", "사용자 지정", "tersuai"],
  data: ["数据", "données", "Daten", "данные", "データ", "데이터", "data"],
  database: ["数据库", "base de données", "Datenbank", "база данных", "データベース", "데이터베이스", "pangkalan data"],
  dataset: ["数据集", "jeu de données", "Datensatz", "набор данных", "データセット", "데이터 세트", "set data"],
  delete: ["删除", "supprimer", "löschen", "удалить", "削除", "삭제", "padam"],
  default: ["默认", "par défaut", "Standard", "по умолчанию", "既定", "기본", "lalai"],
  description: ["描述", "description", "Beschreibung", "описание", "説明", "설명", "penerangan"],
  details: ["详细信息", "détails", "Details", "сведения", "詳細", "세부 정보", "butiran"],
  difference: ["差异", "différence", "Differenz", "разница", "差分", "차이", "perbezaan"],
  difficulty: ["难度", "difficulté", "Schwierigkeit", "сложность", "難易度", "난이도", "kesukaran"],
  disable: ["禁用", "désactiver", "deaktivieren", "отключить", "無効化", "비활성화", "nyahdayakan"],
  disk: ["磁盘", "disque", "Datenträger", "диск", "ディスク", "디스크", "cakera"],
  display: ["显示", "affichage", "Anzeige", "отображение", "表示", "표시", "paparan"],
  download: ["下载", "télécharger", "herunterladen", "скачать", "ダウンロード", "다운로드", "muat turun"],
  edit: ["编辑", "modifier", "bearbeiten", "изменить", "編集", "편집", "sunting"],
  email: ["电子邮件", "e-mail", "E-Mail", "электронная почта", "メール", "이메일", "e-mel"],
  enable: ["启用", "activer", "aktivieren", "включить", "有効化", "활성화", "dayakan"],
  endpoint: ["端点", "point de terminaison", "Endpunkt", "конечная точка", "エンドポイント", "엔드포인트", "titik akhir"],
  endpoints: ["端点", "points de terminaison", "Endpunkte", "конечные точки", "エンドポイント", "엔드포인트", "titik akhir"],
  error: ["错误", "erreur", "Fehler", "ошибка", "エラー", "오류", "ralat"],
  errors: ["错误", "erreurs", "Fehler", "ошибки", "エラー", "오류", "ralat"],
  evidence: ["证据", "preuve", "Nachweis", "доказательство", "証拠", "증거", "bukti"],
  evaluation: ["评测", "évaluation", "Bewertung", "оценка", "評価", "평가", "penilaian"],
  events: ["事件", "événements", "Ereignisse", "события", "イベント", "이벤트", "peristiwa"],
  execution: ["执行", "exécution", "Ausführung", "выполнение", "実行", "실행", "pelaksanaan"],
  executed: ["已执行", "exécutée", "ausgeführt", "выполнен", "実行済み", "실행됨", "dilaksanakan"],
  file: ["文件", "fichier", "Datei", "файл", "ファイル", "파일", "fail"],
  filters: ["筛选器", "filtres", "Filter", "фильтры", "フィルター", "필터", "penapis"],
  form: ["表单", "formulaire", "Formular", "форма", "フォーム", "양식", "borang"],
  generate: ["生成", "générer", "generieren", "создать", "生成", "생성", "jana"],
  generated: ["已生成", "généré", "generiert", "создан", "生成済み", "생성됨", "dijana"],
  guidance: ["指导", "guide", "Leitfaden", "руководство", "ガイダンス", "안내", "panduan"],
  health: ["健康", "santé", "Zustand", "состояние", "正常性", "상태", "kesihatan"],
  human: ["人工", "humain", "menschlich", "человек", "人間", "사람", "manusia"],
  input: ["输入", "entrée", "Eingabe", "ввод", "入力", "입력", "input"],
  inventory: ["清单", "inventaire", "Bestand", "инвентарь", "インベントリ", "인벤토리", "inventori"],
  inspect: ["查看", "inspecter", "prüfen", "проверить", "確認", "검사", "periksa"],
  judge: ["裁判", "juge", "Bewertung", "судья", "判定", "심사", "penilai"],
  language: ["语言", "langue", "Sprache", "язык", "言語", "언어", "bahasa"],
  latency: ["延迟", "latence", "Latenz", "задержка", "レイテンシ", "지연 시간", "kependaman"],
  license: ["许可证", "licence", "Lizenz", "лицензия", "ライセンス", "라이선스", "lesen"],
  live: ["实时", "en direct", "live", "в реальном времени", "ライブ", "실시간", "langsung"],
  load: ["加载", "charger", "laden", "загрузить", "読み込む", "불러오기", "muatkan"],
  loading: ["正在加载", "chargement", "wird geladen", "загрузка", "読み込み中", "불러오는 중", "memuatkan"],
  local: ["本地", "local", "lokal", "локальный", "ローカル", "로컬", "setempat"],
  log: ["日志", "journal", "Protokoll", "журнал", "ログ", "로그", "log"],
  media: ["媒体", "média", "Medien", "медиа", "メディア", "미디어", "media"],
  multi: ["多", "multi", "mehrere", "несколько", "複数", "다중", "berbilang"],
  model: ["模型", "modèle", "Modell", "модель", "モデル", "모델", "model"],
  name: ["名称", "nom", "Name", "имя", "名前", "이름", "nama"],
  new: ["新建", "nouveau", "neu", "новый", "新規", "새", "baharu"],
  next: ["下一步", "suivant", "nächste", "следующий", "次", "다음", "seterusnya"],
  no: ["无", "aucun", "keine", "нет", "なし", "없음", "tiada"],
  not: ["未", "non", "nicht", "не", "ない", "아님", "tidak"],
  notes: ["备注", "notes", "Notizen", "примечания", "メモ", "메모", "nota"],
  of: ["的", "de", "von", "из", "の", "의", "daripada"],
  on: ["在", "sur", "auf", "на", "で", "에서", "pada"],
  only: ["仅", "seulement", "nur", "только", "のみ", "만", "sahaja"],
  operating: ["运行", "opérationnel", "Betrieb", "операционный", "運用", "운영", "operasi"],
  open: ["打开", "ouvrir", "öffnen", "открыть", "開く", "열기", "buka"],
  operation: ["操作", "opération", "Vorgang", "операция", "操作", "작업", "operasi"],
  optional: ["可选", "facultatif", "optional", "необязательный", "任意", "선택 사항", "pilihan"],
  output: ["输出", "sortie", "Ausgabe", "вывод", "出力", "출력", "output"],
  package: ["包", "package", "Paket", "пакет", "パッケージ", "패키지", "pakej"],
  pause: ["暂停", "mettre en pause", "pausieren", "приостановить", "一時停止", "일시 중지", "jeda"],
  paused: ["已暂停", "mise en pause", "pausiert", "приостановлен", "一時停止済み", "일시 중지됨", "dijeda"],
  pending: ["待处理", "en attente", "ausstehend", "ожидающий", "保留中", "보류", "menunggu"],
  preflight: ["预检", "pré-vérification", "Vorprüfung", "предпроверка", "事前確認", "사전 점검", "pra-semak"],
  preferences: ["偏好", "préférences", "Einstellungen", "предпочтения", "設定", "환경설정", "keutamaan"],
  priority: ["优先级", "priorité", "Priorität", "приоритет", "優先度", "우선순위", "keutamaan"],
  production: ["生产", "production", "Produktion", "производство", "本番", "프로덕션", "pengeluaran"],
  prompt: ["提示词", "invite", "Prompt", "запрос", "プロンプト", "프롬프트", "gesaan"],
  provider: ["提供方", "fournisseur", "Anbieter", "поставщик", "プロバイダー", "공급자", "penyedia"],
  queue: ["队列", "file", "Warteschlange", "очередь", "キュー", "대기열", "baris"],
  queued: ["已排队", "en file", "eingereiht", "в очереди", "キュー済み", "대기열에 있음", "dibariskan"],
  raw: ["原始", "brut", "roh", "необработанный", "生", "원시", "mentah"],
  ready: ["就绪", "prêt", "bereit", "готов", "準備完了", "준비됨", "sedia"],
  register: ["注册", "enregistrer", "registrieren", "зарегистрировать", "登録", "등록", "daftar"],
  registry: ["注册表", "registre", "Registrierung", "реестр", "レジストリ", "레지스트리", "daftar"],
  related: ["相关", "associé", "zugehörig", "связанный", "関連", "관련", "berkaitan"],
  remove: ["移除", "supprimer", "entfernen", "удалить", "削除", "제거", "alih keluar"],
  report: ["报告", "rapport", "Bericht", "отчёт", "レポート", "보고서", "laporan"],
  reporting: ["报告", "rapports", "Berichterstellung", "отчётность", "レポート", "보고", "pelaporan"],
  request: ["请求", "requête", "Anfrage", "запрос", "リクエスト", "요청", "permintaan"],
  requests: ["请求", "requêtes", "Anfragen", "запросы", "リクエスト", "요청", "permintaan"],
  required: ["必填", "requis", "erforderlich", "обязательный", "必須", "필수", "diperlukan"],
  response: ["响应", "réponse", "Antwort", "ответ", "応答", "응답", "respons"],
  resume: ["恢复", "reprendre", "fortsetzen", "возобновить", "再開", "재개", "sambung"],
  resumed: ["已恢复", "reprise", "fortgesetzt", "возобновлён", "再開済み", "재개됨", "disambung"],
  retry: ["重试", "réessayer", "wiederholen", "повторить", "再試行", "재시도", "cuba lagi"],
  review: ["审查", "révision", "Überprüfung", "проверка", "レビュー", "검토", "semakan"],
  reviewer: ["审查者", "évaluateur", "Prüfer", "рецензент", "レビュアー", "검토자", "penyemak"],
  row: ["行", "ligne", "Zeile", "строка", "行", "행", "baris"],
  run: ["运行", "exécution", "Ausführung", "запуск", "実行", "실행", "larian"],
  runs: ["运行", "exécutions", "Ausführungen", "запуски", "実行", "실행", "larian"],
  sample: ["样本", "échantillon", "Stichprobe", "образец", "サンプル", "샘플", "sampel"],
  samples: ["样本", "échantillons", "Stichproben", "образцы", "サンプル", "샘플", "sampel"],
  save: ["保存", "enregistrer", "speichern", "сохранить", "保存", "저장", "simpan"],
  score: ["得分", "score", "Punktzahl", "оценка", "スコア", "점수", "skor"],
  search: ["搜索", "rechercher", "suchen", "поиск", "検索", "검색", "cari"],
  select: ["选择", "sélectionner", "auswählen", "выбрать", "選択", "선택", "pilih"],
  selected: ["已选择", "sélectionné", "ausgewählt", "выбранный", "選択済み", "선택됨", "dipilih"],
  settings: ["设置", "paramètres", "Einstellungen", "настройки", "設定", "설정", "tetapan"],
  share: ["共享", "partager", "teilen", "поделиться", "共有", "공유", "kongsi"],
  source: ["来源", "source", "Quelle", "источник", "ソース", "소스", "sumber"],
  status: ["状态", "statut", "Status", "статус", "状態", "상태", "status"],
  storage: ["存储", "stockage", "Speicher", "хранилище", "ストレージ", "저장소", "storan"],
  suite: ["套件", "suite", "Suite", "набор", "スイート", "스위트", "set"],
  system: ["系统", "système", "System", "система", "システム", "시스템", "sistem"],
  task: ["任务", "tâche", "Aufgabe", "задача", "タスク", "작업", "tugas"],
  test: ["测试", "tester", "testen", "тест", "テスト", "테스트", "uji"],
  theme: ["主题", "thème", "Design", "тема", "テーマ", "테마", "tema"],
  this: ["此", "ce", "dieses", "этот", "この", "이", "ini"],
  tokens: ["令牌", "jetons", "Token", "токены", "トークン", "토큰", "token"],
  total: ["总计", "total", "gesamt", "всего", "合計", "합계", "jumlah"],
  type: ["类型", "type", "Typ", "тип", "種類", "유형", "jenis"],
  unavailable: ["不可用", "indisponible", "nicht verfügbar", "недоступно", "利用不可", "사용 불가", "tidak tersedia"],
  unlimited: ["无限制", "illimité", "unbegrenzt", "без ограничений", "無制限", "무제한", "tanpa had"],
  update: ["更新", "mettre à jour", "aktualisieren", "обновить", "更新", "업데이트", "kemas kini"],
  upload: ["上传", "téléverser", "hochladen", "загрузить", "アップロード", "업로드", "muat naik"],
  user: ["用户", "utilisateur", "Benutzer", "пользователь", "ユーザー", "사용자", "pengguna"],
  users: ["用户", "utilisateurs", "Benutzer", "пользователи", "ユーザー", "사용자", "pengguna"],
  validate: ["验证", "valider", "validieren", "проверить", "検証", "검증", "sahkan"],
  version: ["版本", "version", "Version", "версия", "バージョン", "버전", "versi"],
  view: ["查看", "voir", "anzeigen", "просмотреть", "表示", "보기", "lihat"],
  worker: ["工作节点", "agent", "Worker", "воркер", "ワーカー", "워커", "pekerja"],
  workers: ["工作节点", "agents", "Worker", "воркеры", "ワーカー", "워커", "pekerja"],
  workspace: ["工作区", "espace de travail", "Arbeitsbereich", "рабочее пространство", "ワークスペース", "작업 공간", "ruang kerja"],
  a: ["一个", "un", "ein", "один", "1つの", "하나의", "satu"],
  action: ["操作", "action", "Aktion", "действие", "操作", "작업", "tindakan"],
  an: ["一个", "un", "ein", "один", "1つの", "하나의", "satu"],
  anomalies: ["异常", "anomalies", "Anomalien", "аномалии", "異常", "이상", "anomali"],
  answer: ["答案", "réponse", "Antwort", "ответ", "回答", "답변", "jawapan"],
  api: ["API", "API", "API", "API", "API", "API", "API"],
  "api-key": ["API 密钥", "clé API", "API-Schlüssel", "ключ API", "API キー", "API 키", "kunci API"],
  are: ["是", "sont", "sind", "являются", "です", "입니다", "ialah"],
  array: ["数组", "tableau", "Array", "массив", "配列", "배열", "tatasusunan"],
  attached: ["已附加", "joint", "angehängt", "прикреплён", "添付済み", "첨부됨", "dilampirkan"],
  audio: ["音频", "audio", "Audio", "аудио", "音声", "오디오", "audio"],
  base: ["基础", "base", "Basis", "база", "ベース", "기본", "asas"],
  been: ["已", "été", "gewesen", "был", "済み", "됨", "telah"],
  before: ["之前", "avant", "vor", "до", "前", "이전", "sebelum"],
  "benchmark-forced": ["基准强制", "imposé par le référentiel", "Benchmark-erzwungen", "принудительный бенчмарком", "ベンチマーク強制", "벤치마크 강제", "dipaksa penanda aras"],
  benchmarks: ["基准", "référentiels", "Benchmarks", "бенчмарки", "ベンチマーク", "벤치마크", "penanda aras"],
  binding: ["绑定", "liaison", "Bindung", "привязка", "バインド", "바인딩", "pengikatan"],
  "built-in": ["内置", "intégré", "integriert", "встроенный", "組み込み", "내장", "terbina dalam"],
  by: ["由", "par", "von", "по", "により", "으로", "oleh"],
  capabilities: ["能力", "capacités", "Fähigkeiten", "возможности", "機能", "기능", "keupayaan"],
  checking: ["正在检查", "vérification", "Prüfung", "проверка", "確認中", "확인 중", "menyemak"],
  checksum: ["校验和", "somme de contrôle", "Prüfsumme", "контрольная сумма", "チェックサム", "체크섬", "jumlah semak"],
  "comma-separated": ["逗号分隔", "séparé par des virgules", "kommagetrennt", "разделённый запятыми", "カンマ区切り", "쉼표로 구분", "dipisahkan koma"],
  compatibility: ["兼容性", "compatibilité", "Kompatibilität", "совместимость", "互換性", "호환성", "keserasian"],
  completion: ["完成情况", "achèvement", "Abschluss", "завершение", "完了", "완료", "penyiapan"],
  concurrency: ["并发", "concurrence", "Parallelität", "параллелизм", "同時実行", "동시 실행", "serentak"],
  "content-addressed": ["内容寻址", "adressé par contenu", "inhaltsadressiert", "адресуемый содержимым", "コンテンツアドレス", "콘텐츠 주소 지정", "beralamat kandungan"],
  correct: ["正确", "correct", "richtig", "верный", "正解", "정답", "betul"],
  correctness: ["正确性", "exactitude", "Korrektheit", "правильность", "正確性", "정확성", "ketepatan"],
  creating: ["正在创建", "création", "Erstellung", "создание", "作成中", "생성 중", "mencipta"],
  credential: ["凭据", "identifiant", "Anmeldeinformation", "учётные данные", "資格情報", "자격 증명", "kelayakan"],
  currency: ["货币", "devise", "Währung", "валюта", "通貨", "통화", "mata wang"],
  declarations: ["声明", "déclarations", "Deklarationen", "объявления", "宣言", "선언", "perisytiharan"],
  defaults: ["默认值", "valeurs par défaut", "Standardwerte", "значения по умолчанию", "既定値", "기본값", "nilai lalai"],
  detected: ["已检测", "détecté", "erkannt", "обнаружен", "検出済み", "감지됨", "dikesan"],
  detection: ["检测", "détection", "Erkennung", "обнаружение", "検出", "감지", "pengesanan"],
  disagreement: ["分歧", "désaccord", "Uneinigkeit", "разногласие", "不一致", "불일치", "ketidaksetujuan"],
  downloads: ["下载", "téléchargements", "Downloads", "загрузки", "ダウンロード", "다운로드", "muat turun"],
  durable: ["持久", "durable", "beständig", "долговечный", "永続", "지속", "kekal"],
  encrypted: ["已加密", "chiffré", "verschlüsselt", "зашифрованный", "暗号化済み", "암호화됨", "disulitkan"],
  enter: ["输入", "saisir", "eingeben", "ввести", "入力", "입력", "masukkan"],
  entry: ["条目", "entrée", "Eintrag", "запись", "エントリ", "항목", "entri"],
  estimate: ["估算", "estimer", "schätzen", "оценить", "見積もる", "추정", "anggar"],
  examples: ["示例", "exemples", "Beispiele", "примеры", "例", "예시", "contoh"],
  executive: ["执行", "exécutif", "Management", "исполнительный", "エグゼクティブ", "요약", "eksekutif"],
  expected: ["预期", "attendu", "erwartet", "ожидаемый", "期待", "예상", "dijangka"],
  failed: ["失败", "échoué", "fehlgeschlagen", "сбой", "失敗", "실패", "gagal"],
  "few-shot": ["少样本", "few-shot", "Few-Shot", "few-shot", "少数例", "퓨샷", "few-shot"],
  fields: ["字段", "champs", "Felder", "поля", "フィールド", "필드", "medan"],
  files: ["文件", "fichiers", "Dateien", "файлы", "ファイル", "파일", "fail"],
  first: ["首次", "premier", "erste", "первый", "最初", "첫 번째", "pertama"],
  for: ["用于", "pour", "für", "для", "のため", "용", "untuk"],
  format: ["格式", "format", "Format", "формат", "形式", "형식", "format"],
  from: ["来自", "depuis", "von", "из", "から", "에서", "daripada"],
  has: ["有", "a", "hat", "имеет", "ある", "있음", "mempunyai"],
  have: ["有", "ont", "haben", "имеют", "ある", "있음", "mempunyai"],
  headers: ["标头", "en-têtes", "Header", "заголовки", "ヘッダー", "헤더", "pengepala"],
  https: ["HTTPS", "HTTPS", "HTTPS", "HTTPS", "HTTPS", "HTTPS", "HTTPS"],
  id: ["ID", "ID", "ID", "ID", "ID", "ID", "ID"],
  image: ["图像", "image", "Bild", "изображение", "画像", "이미지", "imej"],
  incorrect: ["不正确", "incorrect", "falsch", "неверный", "不正解", "오답", "salah"],
  is: ["是", "est", "ist", "является", "です", "입니다", "ialah"],
  json: ["JSON", "JSON", "JSON", "JSON", "JSON", "JSON", "JSON"],
  key: ["密钥", "clé", "Schlüssel", "ключ", "キー", "키", "kunci"],
  keys: ["密钥", "clés", "Schlüssel", "ключи", "キー", "키", "kunci"],
  "language-specific": ["特定语言", "spécifique à la langue", "sprachspezifisch", "языковой", "言語固有", "언어별", "khusus bahasa"],
  licenses: ["许可证", "licences", "Lizenzen", "лицензии", "ライセンス", "라이선스", "lesen"],
  lifecycle: ["生命周期", "cycle de vie", "Lebenszyklus", "жизненный цикл", "ライフサイクル", "수명 주기", "kitar hayat"],
  loaded: ["已加载", "chargé", "geladen", "загружен", "読み込み済み", "로드됨", "dimuatkan"],
  m: ["百万", "M", "M", "млн", "M", "M", "J"],
  manage: ["管理", "gérer", "verwalten", "управлять", "管理", "관리", "urus"],
  managed: ["受管理", "géré", "verwaltet", "управляемый", "管理済み", "관리됨", "diuruskan"],
  match: ["匹配", "correspondre", "abgleichen", "сопоставить", "一致", "일치", "padan"],
  memory: ["内存", "mémoire", "Speicher", "память", "メモリ", "메모리", "memori"],
  merged: ["已合并", "fusionné", "zusammengeführt", "объединён", "マージ済み", "병합됨", "digabungkan"],
  message: ["消息", "message", "Nachricht", "сообщение", "メッセージ", "메시지", "mesej"],
  mime: ["MIME", "MIME", "MIME", "MIME", "MIME", "MIME", "MIME"],
  minute: ["分钟", "minute", "Minute", "минута", "分", "분", "minit"],
  modalities: ["模态", "modalités", "Modalitäten", "модальности", "モダリティ", "모달리티", "modaliti"],
  modality: ["模态", "modalité", "Modalität", "модальность", "モダリティ", "모달리티", "modaliti"],
  models: ["模型", "modèles", "Modelle", "модели", "モデル", "모델", "model"],
  multimodal: ["多模态", "multimodal", "multimodal", "мультимодальный", "マルチモーダル", "멀티모달", "multimodal"],
  never: ["绝不", "jamais", "nie", "никогда", "決して", "절대", "tidak pernah"],
  none: ["无", "aucun", "keine", "нет", "なし", "없음", "tiada"],
  official: ["官方", "officiel", "offiziell", "официальный", "公式", "공식", "rasmi"],
  or: ["或", "ou", "oder", "или", "または", "또는", "atau"],
  outside: ["外部", "hors", "außerhalb", "вне", "外部", "외부", "di luar"],
  override: ["覆盖", "remplacement", "Überschreibung", "переопределение", "上書き", "재정의", "gantian"],
  overrides: ["覆盖", "remplacements", "Überschreibungen", "переопределения", "上書き", "재정의", "gantian"],
  pack: ["包", "pack", "Paket", "пакет", "パック", "팩", "pek"],
  page: ["页面", "page", "Seite", "страница", "ページ", "페이지", "halaman"],
  parser: ["解析器", "analyseur", "Parser", "парсер", "パーサー", "파서", "penghurai"],
  pdf: ["PDF", "PDF", "PDF", "PDF", "PDF", "PDF", "PDF"],
  platform: ["平台", "plateforme", "Plattform", "платформа", "プラットフォーム", "플랫폼", "platform"],
  preview: ["预览", "aperçu", "Vorschau", "предпросмотр", "プレビュー", "미리보기", "pratonton"],
  probe: ["探测", "sonder", "prüfen", "зондировать", "検出", "탐색", "siasat"],
  probing: ["探测", "sondage", "Sondierung", "зондирование", "検出", "탐색", "siasatan"],
  profile: ["配置文件", "profil", "Profil", "профиль", "プロファイル", "프로필", "profil"],
  protocol: ["协议", "protocole", "Protokoll", "протокол", "プロトコル", "프로토콜", "protokol"],
  quick: ["快速", "rapide", "schnell", "быстрый", "クイック", "빠른", "pantas"],
  recorded: ["已记录", "enregistré", "aufgezeichnet", "записан", "記録済み", "기록됨", "direkodkan"],
  refreshes: ["刷新", "s’actualise", "aktualisiert", "обновляется", "更新", "새로고침", "menyegar semula"],
  regressions: ["回归", "régressions", "Regressionen", "регрессии", "回帰", "회귀", "regresi"],
  remain: ["保持", "restent", "bleiben", "остаются", "維持", "유지", "kekal"],
  result: ["结果", "résultat", "Ergebnis", "результат", "結果", "결과", "hasil"],
  return: ["返回", "retourner", "zurückgeben", "вернуть", "返す", "반환", "kembali"],
  revision: ["修订", "révision", "Revision", "редакция", "改訂", "개정", "semakan"],
  rule: ["规则", "règle", "Regel", "правило", "ルール", "규칙", "peraturan"],
  running: ["运行中", "en cours", "laufend", "выполняется", "実行中", "실행 중", "berjalan"],
  saved: ["已保存", "enregistré", "gespeichert", "сохранён", "保存済み", "저장됨", "disimpan"],
  saving: ["正在保存", "enregistrement", "speichert", "сохранение", "保存中", "저장 중", "menyimpan"],
  scored: ["已评分", "noté", "bewertet", "оценён", "採点済み", "채점됨", "dinilai"],
  scoring: ["评分", "notation", "Bewertung", "оценивание", "採点", "채점", "pemarkahan"],
  second: ["秒", "seconde", "Sekunde", "секунда", "秒", "초", "saat"],
  separate: ["分开", "séparé", "getrennt", "отдельный", "分離", "분리", "asing"],
  sha: ["SHA", "SHA", "SHA", "SHA", "SHA", "SHA", "SHA"],
  shared: ["共享", "partagé", "geteilt", "общий", "共有", "공유", "dikongsi"],
  signals: ["信号", "signaux", "Signale", "сигналы", "シグナル", "신호", "isyarat"],
  signature: ["签名", "signature", "Signatur", "подпись", "署名", "서명", "tandatangan"],
  single: ["单", "unique", "einzel", "одна", "単一", "단일", "tunggal"],
  significant: ["显著", "significatif", "signifikant", "значительный", "重要", "중요", "ketara"],
  snapshot: ["快照", "instantané", "Snapshot", "снимок", "スナップショット", "스냅샷", "petikan"],
  states: ["状态", "états", "Zustände", "состояния", "状態", "상태", "keadaan"],
  still: ["仍然", "toujours", "weiterhin", "всё ещё", "まだ", "여전히", "masih"],
  stored: ["已存储", "stocké", "gespeichert", "сохранён", "保存済み", "저장됨", "disimpan"],
  succeeded: ["成功", "réussi", "erfolgreich", "успешно", "成功", "성공", "berjaya"],
  suites: ["套件", "suites", "Suiten", "наборы", "スイート", "스위트", "set"],
  summary: ["摘要", "résumé", "Zusammenfassung", "сводка", "概要", "요약", "ringkasan"],
  supported: ["受支持", "pris en charge", "unterstützt", "поддерживается", "対応", "지원됨", "disokong"],
  tags: ["标签", "étiquettes", "Tags", "теги", "タグ", "태그", "tag"],
  template: ["模板", "modèle", "Vorlage", "шаблон", "テンプレート", "템플릿", "templat"],
  tests: ["测试", "tests", "Tests", "тесты", "テスト", "테스트", "ujian"],
  text: ["文本", "texte", "Text", "текст", "テキスト", "텍스트", "teks"],
  the: ["该", "le", "der", "этот", "その", "해당", "itu"],
  these: ["这些", "ces", "diese", "эти", "これら", "이러한", "ini"],
  they: ["它们", "ils", "sie", "они", "それら", "그것들", "mereka"],
  to: ["到", "à", "zu", "к", "へ", "에", "ke"],
  unknown: ["未知", "inconnu", "unbekannt", "неизвестный", "不明", "알 수 없음", "tidak diketahui"],
  unsupported: ["不支持", "non pris en charge", "nicht unterstützt", "не поддерживается", "未対応", "지원되지 않음", "tidak disokong"],
  uploaded: ["已上传", "téléversé", "hochgeladen", "загружен", "アップロード済み", "업로드됨", "dimuat naik"],
  uploading: ["正在上传", "téléversement", "Hochladen", "загрузка", "アップロード中", "업로드 중", "memuat naik"],
  url: ["URL", "URL", "URL", "URL", "URL", "URL", "URL"],
  use: ["使用", "utiliser", "verwenden", "использовать", "使用", "사용", "guna"],
  validated: ["已验证", "validé", "validiert", "проверен", "検証済み", "검증됨", "disahkan"],
  validating: ["正在验证", "validation", "Validierung", "проверка", "検証中", "검증 중", "mengesahkan"],
  variant: ["变体", "variante", "Variante", "вариант", "バリアント", "변형", "varian"],
  verify: ["验证", "vérifier", "prüfen", "проверить", "確認", "검증", "sahkan"],
  versioned: ["已版本化", "versionné", "versioniert", "версионированный", "バージョン管理済み", "버전 관리됨", "berversi"],
  video: ["视频", "vidéo", "Video", "видео", "動画", "비디오", "video"],
  vision: ["视觉", "vision", "Vision", "зрение", "ビジョン", "비전", "penglihatan"],
  weight: ["权重", "poids", "Gewichtung", "вес", "重み", "가중치", "berat"],
  win: ["胜出", "gagner", "gewinnen", "победить", "勝つ", "승리", "menang"],
  with: ["带有", "avec", "mit", "с", "と", "함께", "dengan"],
  without: ["没有", "sans", "ohne", "без", "なしで", "없이", "tanpa"],
  work: ["工作", "travail", "Arbeit", "работа", "作業", "작업", "kerja"],
  yet: ["尚未", "encore", "noch", "ещё", "まだ", "아직", "lagi"],
};

const protocolProfilePhrases: Record<Locale, Record<string, string>> = {
  en: {},
  "zh-CN": {
    "Access and preferences": "访问和偏好设置",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "配置受限的 API 用户，并将最近的管理活动与当前清单一同保留。",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "在打开人工或独立评审工作流前，选择评测快照和样本。",
    "Overview": "概览", "Configure": "配置", "Catalog": "目录", "Operations": "运行", "Insights": "洞察", "Reporting": "报告", "Quality review": "质量审核", "Administration": "管理", "Evaluation workflow": "评测工作流",
    "OpenAI-compatible Chat Completions": "兼容 OpenAI 的聊天补全",
    "OpenAI-compatible Responses API": "兼容 OpenAI 的 Responses API",
    "Anthropic Messages": "Anthropic 消息 API",
    "Gemini GenerateContent": "Gemini 内容生成",
    "Azure OpenAI Chat Completions": "Azure OpenAI 聊天补全",
    "Ollama Chat": "Ollama 聊天",
    "Custom HTTP JSON": "自定义 HTTP JSON",
  },
  fr: {
    "Operating guidance": "Guide d’utilisation",
    "User inventory": "Inventaire des utilisateurs",
    "Review run": "Exécution à examiner",
    "Overview": "Vue d’ensemble", "Configure": "Configurer", "Catalog": "Catalogue", "Operations": "Opérations", "Insights": "Analyses", "Reporting": "Rapports", "Quality review": "Revue qualité", "Administration": "Administration", "Evaluation workflow": "Flux de travail d’évaluation",
    "OpenAI-compatible Chat Completions": "Complétions de chat compatibles OpenAI",
    "OpenAI-compatible Responses API": "API Responses compatible OpenAI",
    "Anthropic Messages": "Messages Anthropic",
    "Gemini GenerateContent": "Génération de contenu Gemini",
    "Azure OpenAI Chat Completions": "Complétions de chat Azure OpenAI",
    "Ollama Chat": "Chat Ollama",
    "Custom HTTP JSON": "JSON HTTP personnalisé",
  },
  de: {
    "Name, source, status…": "Name, Quelle, Status…",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "Erstellen Sie ein tokenbasiertes Konto mit der geringsten Berechtigung und einer optionalen Parallelitätsobergrenze.",
    "Review sample": "Zu prüfende Stichprobe",
    "Overview": "Übersicht", "Configure": "Konfigurieren", "Catalog": "Katalog", "Operations": "Betrieb", "Insights": "Erkenntnisse", "Reporting": "Berichte", "Quality review": "Qualitätsprüfung", "Administration": "Verwaltung", "Evaluation workflow": "Bewertungsablauf",
    "OpenAI-compatible Chat Completions": "OpenAI-kompatible Chat-Vervollständigungen",
    "OpenAI-compatible Responses API": "OpenAI-kompatible Responses-API",
    "Anthropic Messages": "Anthropic Messages",
    "Gemini GenerateContent": "Gemini-Inhaltsgenerierung",
    "Azure OpenAI Chat Completions": "Azure OpenAI Chat-Vervollständigungen",
    "Ollama Chat": "Ollama-Chat",
    "Custom HTTP JSON": "Benutzerdefiniertes HTTP-JSON",
  },
  ru: {
    "Benchmark, status, or ID": "Бенчмарк, статус или идентификатор",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "Роли, ограничения частоты и статус остаются видимыми перед выпуском дополнительных учётных данных.",
    "Select a run to begin a human or judge review.": "Выберите запуск, чтобы начать проверку человеком или судьёй.",
    "Overview": "Обзор", "Configure": "Настройка", "Catalog": "Каталог", "Operations": "Операции", "Insights": "Аналитика", "Reporting": "Отчёты", "Quality review": "Проверка качества", "Administration": "Администрирование", "Evaluation workflow": "Рабочий процесс оценки",
    "OpenAI-compatible Chat Completions": "Совместимые с OpenAI чат-завершения",
    "OpenAI-compatible Responses API": "Совместимый с OpenAI API Responses",
    "Anthropic Messages": "Сообщения Anthropic",
    "Gemini GenerateContent": "Генерация контента Gemini",
    "Azure OpenAI Chat Completions": "Чат-завершения Azure OpenAI",
    "Ollama Chat": "Чат Ollama",
    "Custom HTTP JSON": "Пользовательский HTTP JSON",
  },
  ja: {
    "total runs": "総実行数",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "最新の記録済み管理変更は、ユーザー作成値とは分けて監査証跡として保持されます。",
    "Human review workflow": "人によるレビューのワークフロー",
    "Overview": "概要", "Configure": "設定", "Catalog": "カタログ", "Operations": "運用", "Insights": "インサイト", "Reporting": "レポート", "Quality review": "品質レビュー", "Administration": "管理", "Evaluation workflow": "評価ワークフロー",
    "OpenAI-compatible Chat Completions": "OpenAI 互換チャット補完",
    "OpenAI-compatible Responses API": "OpenAI 互換 Responses API",
    "Anthropic Messages": "Anthropic メッセージ API",
    "Gemini GenerateContent": "Gemini コンテンツ生成",
    "Azure OpenAI Chat Completions": "Azure OpenAI チャット補完",
    "Ollama Chat": "Ollama チャット",
    "Custom HTTP JSON": "カスタム HTTP JSON",
  },
  ko: {
    "Overview": "개요", "Configure": "구성", "Catalog": "카탈로그", "Operations": "운영", "Insights": "인사이트", "Reporting": "보고", "Quality review": "품질 검토", "Administration": "관리", "Evaluation workflow": "평가 워크플로",
    "OpenAI-compatible Chat Completions": "OpenAI 호환 채팅 완성",
    "OpenAI-compatible Responses API": "OpenAI 호환 Responses API",
    "Anthropic Messages": "Anthropic 메시지 API",
    "Gemini GenerateContent": "Gemini 콘텐츠 생성",
    "Azure OpenAI Chat Completions": "Azure OpenAI 채팅 완성",
    "Ollama Chat": "Ollama 채팅",
    "Custom HTTP JSON": "사용자 지정 HTTP JSON",
  },
  ms: {
    "Overview": "Gambaran keseluruhan", "Configure": "Konfigurasi", "Catalog": "Katalog", "Operations": "Operasi", "Insights": "Cerapan", "Reporting": "Pelaporan", "Quality review": "Semakan kualiti", "Administration": "Pentadbiran", "Evaluation workflow": "Aliran kerja penilaian",
    "OpenAI-compatible Chat Completions": "Pelengkapan sembang serasi OpenAI",
    "OpenAI-compatible Responses API": "API Responses serasi OpenAI",
    "Anthropic Messages": "Mesej Anthropic",
    "Gemini GenerateContent": "Penjanaan kandungan Gemini",
    "Azure OpenAI Chat Completions": "Pelengkapan sembang Azure OpenAI",
    "Ollama Chat": "Sembang Ollama",
    "Custom HTTP JSON": "HTTP JSON tersuai",
  },
};

const phrases: Record<Locale, Record<string, string>> = {
  en: {},
  "zh-CN": { "Add model endpoint": "添加模型端点", "Run configuration": "运行配置", "No model endpoints yet.": "尚无模型端点。", "Model capabilities": "模型能力", "Evaluation suites": "评测套件", "System settings": "系统设置", "Human review": "人工审查", "Data preview": "数据预览", "Delete dataset version?": "删除数据集版本？", "Save changes": "保存更改", "Dataset version updated.": "数据集版本已更新。", "Dataset version deleted.": "数据集版本已删除。", "Preview unavailable.": "预览不可用。", "How to use this workspace": "如何使用此工作区", "1. Add a model endpoint": "1. 添加模型端点", "2. Register a dataset": "2. 注册数据集", "3. Download and verify": "3. 下载并验证", "4. Create a prompt package": "4. 创建提示词包", "5. Queue a dataset run": "5. 将数据集评测加入队列", "6. Inspect evidence": "6. 检查证据", "7. Judge, review, and report": "7. 评审、审核并生成报告", "6 steps": "6 个步骤", "4. Queue a dataset run": "4. 将数据集评测加入队列", "5. Inspect evidence": "5. 检查证据", "6. Analyze results": "6. 分析结果", "Runs": "运行", "Datasets": "数据集", "Analysis": "分析", "Open Models": "打开模型", "Open Datasets": "打开数据集", "Review Datasets": "查看数据集", "Open Runs": "打开运行", "Inspect Runs": "检查运行", "Open Analysis": "打开分析", "Selected model endpoint": "所选模型端点", "Select a configured endpoint to inspect it.": "选择已配置的端点以检查它。", "Register a source, then prepare, validate, and inspect it here.": "注册来源，然后在此准备、验证并检查它。", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "从运行清单中选择一个运行，打开其摘要、证据和生命周期历史。", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "检查所提供的质量、可靠性、延迟、成本和运行间证据。", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "每个阶段都会打开一个必要的评测目标，因此指南仍是一条可执行的路径，而非静态清单。", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "运行 · 选择数据集、评测指标、参考字段和端点，然后将运行加入队列。", "Runs · open the run to review samples, scores, latency, cost, and errors.": "运行 · 打开运行以检查样本、得分、延迟、成本和错误。", "Analysis · inspect evaluation dimensions or compare two completed runs.": "分析 · 检查各评测维度或比较两个已完成运行。", "Filter benchmarks": "筛选基准", "Find run": "查找运行", "Run status": "运行状态", "No runs match the current filters.": "没有运行符合当前筛选条件。", "Pause download": "暂停下载", "Validate cache": "验证缓存", "Clear cache": "清除缓存", "Retry download": "重试下载", "Upload local revision": "上传本地修订", "Benchmark composition": "基准组成", "Queue suite": "套件入队", "Uses each selected endpoint’s saved connection and capacity configuration.": "使用每个所选端点保存的连接和容量配置。", "No available endpoints are ready to receive this suite.": "没有可接收此套件的可用端点。", "Loading disk usage…": "正在加载磁盘使用情况…", "No events available.": "暂无可用事件。", "Comparing…": "正在比较…", "registered versions": "已注册版本", "tasks visible": "可见任务", },
  fr: { "Add model endpoint": "Ajouter un point de terminaison de modèle", "Run configuration": "Configuration d’exécution", "No model endpoints yet.": "Aucun point de terminaison de modèle.", "Model capabilities": "Capacités du modèle", "Evaluation suites": "Suites d’évaluation", "System settings": "Paramètres système", "Human review": "Révision humaine", "Data preview": "Aperçu des données", "Delete dataset version?": "Supprimer la version du jeu de données ?", "Save changes": "Enregistrer les modifications", "Dataset version updated.": "Version du jeu de données mise à jour.", "Dataset version deleted.": "Version du jeu de données supprimée.", "Preview unavailable.": "Aperçu indisponible.", "How to use this workspace": "Comment utiliser cet espace de travail", "1. Add a model endpoint": "1. Ajouter un point de terminaison de modèle", "2. Register a dataset": "2. Enregistrer un jeu de données", "3. Download and verify": "3. Télécharger et vérifier", "4. Create a prompt package": "4. Créer un paquet de prompts", "5. Queue a dataset run": "5. Mettre une exécution en file", "6. Inspect evidence": "6. Examiner les preuves", "7. Judge, review, and report": "7. Juger, réviser et rapporter", "6 steps": "6 étapes", "4. Queue a dataset run": "4. Mettre une exécution de jeu de données en file", "5. Inspect evidence": "5. Examiner les preuves", "6. Analyze results": "6. Analyser les résultats", "Runs": "Exécutions", "Datasets": "Jeux de données", "Analysis": "Analyse", "Open Models": "Ouvrir les modèles", "Open Datasets": "Ouvrir les jeux de données", "Review Datasets": "Examiner les jeux de données", "Open Runs": "Ouvrir les exécutions", "Inspect Runs": "Examiner les exécutions", "Open Analysis": "Ouvrir l’analyse", "Selected model endpoint": "Point de terminaison de modèle sélectionné", "Select a configured endpoint to inspect it.": "Sélectionnez un point de terminaison configuré pour l’examiner.", "Register a source, then prepare, validate, and inspect it here.": "Enregistrez une source, puis préparez-la, validez-la et examinez-la ici.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "Sélectionnez une exécution dans l’inventaire des exécutions pour ouvrir son résumé, ses preuves et son historique de cycle de vie.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "Examinez les preuves fournies de qualité, de fiabilité, de latence et de coût, ainsi que les preuves d’une exécution à l’autre.", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "Chaque étape ouvre une destination d’évaluation essentielle, si bien que le guide reste un parcours actionnable plutôt qu’une liste statique.", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "Exécutions · choisissez le jeu de données, la métrique d’évaluation, le champ de référence et le point de terminaison, puis mettez l’exécution en file.", "Runs · open the run to review samples, scores, latency, cost, and errors.": "Exécutions · ouvrez l’exécution pour examiner les échantillons, les scores, la latence, les coûts et les erreurs.", "Analysis · inspect evaluation dimensions or compare two completed runs.": "Analyse · examinez les dimensions d’évaluation ou comparez deux exécutions terminées.", "Filter benchmarks": "Filtrer les référentiels", "Find run": "Rechercher une exécution", "Run status": "Statut de l’exécution", "No runs match the current filters.": "Aucune exécution ne correspond aux filtres actuels.", "Pause download": "Mettre le téléchargement en pause", "Validate cache": "Valider le cache", "Clear cache": "Vider le cache", "Retry download": "Réessayer le téléchargement", "Upload local revision": "Téléverser une révision locale", "Benchmark composition": "Composition du référentiel", "Queue suite": "Mettre la suite en file", "Uses each selected endpoint’s saved connection and capacity configuration.": "Utilise la connexion et la configuration de capacité enregistrées de chaque point de terminaison sélectionné.", "No available endpoints are ready to receive this suite.": "Aucun point de terminaison disponible n’est prêt à recevoir cette suite.", "Loading disk usage…": "Chargement de l’utilisation du disque…", "No events available.": "Aucun événement disponible.", "Comparing…": "Comparaison en cours…", "registered versions": "versions enregistrées", "tasks visible": "tâches visibles", },
  de: { "Add model endpoint": "Modellendpunkt hinzufügen", "Run configuration": "Ausführungskonfiguration", "No model endpoints yet.": "Noch keine Modellendpunkte.", "Model capabilities": "Modellfähigkeiten", "Evaluation suites": "Bewertungssuiten", "System settings": "Systemeinstellungen", "Human review": "Menschliche Überprüfung", "Data preview": "Datenvorschau", "Delete dataset version?": "Datensatzversion löschen?", "Save changes": "Änderungen speichern", "Dataset version updated.": "Datensatzversion aktualisiert.", "Dataset version deleted.": "Datensatzversion gelöscht.", "Preview unavailable.": "Vorschau nicht verfügbar.", "How to use this workspace": "So verwenden Sie diesen Arbeitsbereich", "1. Add a model endpoint": "1. Modellendpunkt hinzufügen", "2. Register a dataset": "2. Datensatz registrieren", "3. Download and verify": "3. Herunterladen und verifizieren", "4. Create a prompt package": "4. Prompt-Paket erstellen", "5. Queue a dataset run": "5. Datensatzlauf einreihen", "6. Inspect evidence": "6. Nachweise prüfen", "7. Judge, review, and report": "7. Bewerten, prüfen und berichten", "6 steps": "6 Schritte", "4. Queue a dataset run": "4. Datensatzlauf einreihen", "5. Inspect evidence": "5. Nachweise prüfen", "6. Analyze results": "6. Ergebnisse analysieren", "Runs": "Ausführungen", "Datasets": "Datensätze", "Analysis": "Analyse", "Open Models": "Modelle öffnen", "Open Datasets": "Datensätze öffnen", "Review Datasets": "Datensätze prüfen", "Open Runs": "Ausführungen öffnen", "Inspect Runs": "Ausführungen prüfen", "Open Analysis": "Analyse öffnen", "Selected model endpoint": "Ausgewählter Modellendpunkt", "Select a configured endpoint to inspect it.": "Wählen Sie einen konfigurierten Endpunkt aus, um ihn zu prüfen.", "Register a source, then prepare, validate, and inspect it here.": "Registrieren Sie eine Quelle und bereiten Sie sie hier vor, validieren Sie sie und prüfen Sie sie.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "Wählen Sie einen Lauf aus der Ausführungsübersicht, um seine Zusammenfassung, Nachweise und den Lebenszyklusverlauf zu öffnen.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "Prüfen Sie die bereitgestellten Nachweise zu Qualität, Zuverlässigkeit, Latenz, Kosten und Lauf-zu-Lauf-Vergleich.", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "Jede Stufe öffnet ein wesentliches Bewertungsziel, sodass der Leitfaden ein ausführbarer Pfad und keine statische Checkliste bleibt.", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "Ausführungen · Wählen Sie Datensatz, Bewertungsmetrik, Referenzfeld und Endpunkt aus und reihen Sie den Lauf dann ein.", "Runs · open the run to review samples, scores, latency, cost, and errors.": "Ausführungen · Öffnen Sie den Lauf, um Stichproben, Punktzahlen, Latenz, Kosten und Fehler zu prüfen.", "Analysis · inspect evaluation dimensions or compare two completed runs.": "Analyse · Prüfen Sie Bewertungsdimensionen oder vergleichen Sie zwei abgeschlossene Läufe.", "Filter benchmarks": "Benchmarks filtern", "Find run": "Ausführung suchen", "Run status": "Ausführungsstatus", "No runs match the current filters.": "Keine Ausführung entspricht den aktuellen Filtern.", "Pause download": "Download pausieren", "Validate cache": "Cache validieren", "Clear cache": "Cache leeren", "Retry download": "Download wiederholen", "Upload local revision": "Lokale Revision hochladen", "Benchmark composition": "Benchmark-Zusammenstellung", "Queue suite": "Suite einreihen", "Uses each selected endpoint’s saved connection and capacity configuration.": "Verwendet die gespeicherte Verbindung und Kapazitätskonfiguration jedes ausgewählten Endpunkts.", "No available endpoints are ready to receive this suite.": "Kein verfügbarer Endpunkt ist bereit, diese Suite zu empfangen.", "Loading disk usage…": "Speicherplatz wird geladen…", "No events available.": "Keine Ereignisse verfügbar.", "Comparing…": "Vergleiche…", "registered versions": "registrierte Versionen", "tasks visible": "sichtbare Aufgaben", },
  ru: { "Add model endpoint": "Добавить конечную точку модели", "Run configuration": "Конфигурация запуска", "No model endpoints yet.": "Конечных точек модели пока нет.", "Model capabilities": "Возможности модели", "Evaluation suites": "Наборы оценки", "System settings": "Настройки системы", "Human review": "Проверка человеком", "Data preview": "Предпросмотр данных", "Delete dataset version?": "Удалить версию набора данных?", "Save changes": "Сохранить изменения", "Dataset version updated.": "Версия набора данных обновлена.", "Dataset version deleted.": "Версия набора данных удалена.", "Preview unavailable.": "Предпросмотр недоступен.", "How to use this workspace": "Как пользоваться этим рабочим пространством", "1. Add a model endpoint": "1. Добавьте конечную точку модели", "2. Register a dataset": "2. Зарегистрируйте набор данных", "3. Download and verify": "3. Скачайте и проверьте", "4. Create a prompt package": "4. Создайте пакет промптов", "5. Queue a dataset run": "5. Поставьте запуск набора данных в очередь", "6. Inspect evidence": "6. Изучите доказательства", "7. Judge, review, and report": "7. Оцените, проверьте и подготовьте отчёт", "6 steps": "6 шагов", "4. Queue a dataset run": "4. Поставьте запуск набора данных в очередь", "5. Inspect evidence": "5. Изучите доказательства", "6. Analyze results": "6. Проанализируйте результаты", "Runs": "Запуски", "Datasets": "Наборы данных", "Analysis": "Анализ", "Open Models": "Открыть модели", "Open Datasets": "Открыть наборы данных", "Review Datasets": "Просмотреть наборы данных", "Open Runs": "Открыть запуски", "Inspect Runs": "Проверить запуски", "Open Analysis": "Открыть анализ", "Selected model endpoint": "Выбранная конечная точка модели", "Select a configured endpoint to inspect it.": "Выберите настроенную конечную точку, чтобы проверить её.", "Register a source, then prepare, validate, and inspect it here.": "Зарегистрируйте источник, затем подготовьте, проверьте и изучите его здесь.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "Выберите запуск в списке запусков, чтобы открыть его сводку, доказательства и историю жизненного цикла.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "Изучите предоставленные доказательства качества, надёжности, задержки, стоимости и результаты между запусками.", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "Каждый этап открывает важный целевой раздел оценки, поэтому руководство остаётся действующим планом, а не статичным списком.", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "Запуски · выберите набор данных, метрику оценки, поле ссылки и конечную точку, затем поставьте запуск в очередь.", "Runs · open the run to review samples, scores, latency, cost, and errors.": "Запуски · откройте запуск, чтобы просмотреть образцы, оценки, задержку, стоимость и ошибки.", "Analysis · inspect evaluation dimensions or compare two completed runs.": "Анализ · изучите измерения оценки или сравните два завершённых запуска.", "Filter benchmarks": "Фильтр бенчмарков", "Find run": "Найти запуск", "Run status": "Статус запуска", "No runs match the current filters.": "Ни один запуск не соответствует текущим фильтрам.", "Pause download": "Приостановить загрузку", "Validate cache": "Проверить кэш", "Clear cache": "Очистить кэш", "Retry download": "Повторить загрузку", "Upload local revision": "Загрузить локальную редакцию", "Benchmark composition": "Состав бенчмарка", "Queue suite": "Поставить набор в очередь", "Uses each selected endpoint’s saved connection and capacity configuration.": "Использует сохранённые соединение и конфигурацию ёмкости каждого выбранного конечного пункта.", "No available endpoints are ready to receive this suite.": "Нет доступных конечных точек, готовых принять этот набор.", "Loading disk usage…": "Загрузка использования диска…", "No events available.": "События недоступны.", "Comparing…": "Сравнение…", "registered versions": "зарегистрированные версии", "tasks visible": "видимые задачи", },
  ja: { "Add model endpoint": "モデルエンドポイントを追加", "Run configuration": "実行設定", "No model endpoints yet.": "モデルエンドポイントはまだありません。", "Model capabilities": "モデル機能", "Evaluation suites": "評価スイート", "System settings": "システム設定", "Human review": "人によるレビュー", "Data preview": "データのプレビュー", "Delete dataset version?": "データセット バージョンを削除しますか?", "Save changes": "変更を保存", "Dataset version updated.": "データセットのバージョンが更新されました。", "Dataset version deleted.": "データセットのバージョンが削除されました。", "Preview unavailable.": "プレビューを利用できません。", "How to use this workspace": "このワークスペースの使い方", "1. Add a model endpoint": "1. モデルエンドポイントを追加", "2. Register a dataset": "2. データセットを登録", "3. Download and verify": "3. ダウンロードして検証", "4. Create a prompt package": "4. プロンプト パッケージを作成", "5. Queue a dataset run": "5. データセット実行をキューに登録", "6. Inspect evidence": "6. 証拠を確認", "7. Judge, review, and report": "7. 判定、レビュー、レポート", "6 steps": "6 つの手順", "4. Queue a dataset run": "4. データセット実行をキューに登録", "5. Inspect evidence": "5. 証拠を確認", "6. Analyze results": "6. 結果を分析", "Runs": "実行", "Datasets": "データセット", "Analysis": "分析", "Open Models": "モデルを開く", "Open Datasets": "データセットを開く", "Review Datasets": "データセットを確認", "Open Runs": "実行を開く", "Inspect Runs": "実行を確認", "Open Analysis": "分析を開く", "Selected model endpoint": "選択したモデルエンドポイント", "Select a configured endpoint to inspect it.": "設定済みのエンドポイントを選択して確認します。", "Register a source, then prepare, validate, and inspect it here.": "ソースを登録し、ここで準備、検証、確認を行います。", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "実行一覧から実行を選択して、概要、証拠、ライフサイクル履歴を開きます。", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "提供された品質、信頼性、レイテンシ、コスト、実行間の証拠を調査します。", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "各段階で不可欠な評価先が開くため、このガイドは静的なチェックリストではなく実行可能な手順として機能します。", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "実行 · データセット、評価メトリク、参照フィールド、エンドポイントを選択して、実行をキューに登録します。", "Runs · open the run to review samples, scores, latency, cost, and errors.": "実行 · 実行を開いて、サンプル、スコア、レイテンシ、コスト、エラーを確認します。", "Analysis · inspect evaluation dimensions or compare two completed runs.": "分析 · 評価の各側面を確認するか、完了した 2 つの実行を比較します。", "Filter benchmarks": "ベンチマークを絞り込む", "Find run": "実行を検索", "Run status": "実行ステータス", "No runs match the current filters.": "現在のフィルターに一致する実行はありません。", "Pause download": "ダウンロードを一時停止", "Validate cache": "キャッシュを検証", "Clear cache": "キャッシュを消去", "Retry download": "ダウンロードを再試行", "Upload local revision": "ローカル改訂をアップロード", "Benchmark composition": "ベンチマーク構成", "Queue suite": "スイートをキューに追加", "Uses each selected endpoint’s saved connection and capacity configuration.": "選択した各エンドポイントの保存済み接続と容量構成を使用します。", "No available endpoints are ready to receive this suite.": "このスイートを受信できる利用可能なエンドポイントはありません。", "Loading disk usage…": "ディスク使用量を読み込み中…", "No events available.": "利用可能なイベントはありません。", "Comparing…": "比較中…", "registered versions": "登録済みバージョン", "tasks visible": "表示中のタスク", },
  ko: { "Add model endpoint": "모델 엔드포인트 추가", "Run configuration": "실행 구성", "No model endpoints yet.": "모델 엔드포인트가 아직 없습니다.", "Model capabilities": "모델 기능", "Evaluation suites": "평가 스위트", "System settings": "시스템 설정", "Human review": "사람 검토", "Data preview": "데이터 미리보기", "Delete dataset version?": "데이터 세트 버전을 삭제하시겠습니까?", "Save changes": "변경 사항 저장", "Dataset version updated.": "데이터 세트 버전이 업데이트되었습니다.", "Dataset version deleted.": "데이터 세트 버전이 삭제되었습니다.", "Preview unavailable.": "미리보기를 사용할 수 없습니다.", "How to use this workspace": "이 작업 공간 사용 방법", "1. Add a model endpoint": "1. 모델 엔드포인트 추가", "2. Register a dataset": "2. 데이터 세트 등록", "3. Download and verify": "3. 다운로드 및 검증", "4. Create a prompt package": "4. 프롬프트 패키지 만들기", "5. Queue a dataset run": "5. 데이터 세트 실행 대기열에 추가", "6. Inspect evidence": "6. 증거 검토", "7. Judge, review, and report": "7. 판정, 검토 및 보고", "6 steps": "6단계", "4. Queue a dataset run": "4. 데이터 세트 실행을 대기열에 추가", "5. Inspect evidence": "5. 증거 검토", "6. Analyze results": "6. 결과 분석", "Runs": "실행", "Datasets": "데이터 세트", "Analysis": "분석", "Open Models": "모델 열기", "Open Datasets": "데이터 세트 열기", "Review Datasets": "데이터 세트 검토", "Open Runs": "실행 열기", "Inspect Runs": "실행 검토", "Open Analysis": "분석 열기", "Selected model endpoint": "선택한 모델 엔드포인트", "Select a configured endpoint to inspect it.": "구성된 엔드포인트를 선택하여 검사합니다.", "Register a source, then prepare, validate, and inspect it here.": "소스를 등록한 다음 여기에서 준비, 검증 및 검사합니다.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "실행 인벤토리에서 실행을 선택하여 요약, 증거 및 수명 주기 기록을 엽니다.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "제공된 품질, 안정성, 지연 시간, 비용 및 실행 간 증거를 조사합니다.", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "각 단계는 필수 평가 목적지를 열므로 가이드는 정적 체크리스트가 아닌 실행 가능한 경로로 유지됩니다.", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "실행 · 데이터 세트, 평가 메트릭, 참조 필드 및 엔드포인트를 선택한 다음 실행을 대기열에 추가합니다.", "Runs · open the run to review samples, scores, latency, cost, and errors.": "실행 · 실행을 열어 샘플, 점수, 지연 시간, 비용 및 오류를 검토합니다.", "Analysis · inspect evaluation dimensions or compare two completed runs.": "분석 · 평가 차원을 검사하거나 완료된 두 실행을 비교합니다.", "Filter benchmarks": "벤치마크 필터", "Find run": "실행 찾기", "Run status": "실행 상태", "No runs match the current filters.": "현재 필터와 일치하는 실행이 없습니다.", "Pause download": "다운로드 일시 중지", "Validate cache": "캐시 검증", "Clear cache": "캐시 지우기", "Retry download": "다운로드 재시도", "Upload local revision": "로컬 개정 업로드", "Benchmark composition": "벤치마크 구성", "Queue suite": "스위트를 대기열에 추가", "Uses each selected endpoint’s saved connection and capacity configuration.": "선택한 각 엔드포인트의 저장된 연결 및 용량 구성을 사용합니다.", "No available endpoints are ready to receive this suite.": "이 스위트를 받을 준비가 된 사용 가능한 엔드포인트가 없습니다.", "Loading disk usage…": "디스크 사용량을 불러오는 중…", "No events available.": "사용 가능한 이벤트가 없습니다.", "Comparing…": "비교 중…", "registered versions": "등록된 버전", "tasks visible": "표시된 작업", },
  ms: { "Add model endpoint": "Tambah titik akhir model", "Run configuration": "Konfigurasi larian", "No model endpoints yet.": "Belum ada titik akhir model.", "Model capabilities": "Keupayaan model", "Evaluation suites": "Set penilaian", "System settings": "Tetapan sistem", "Human review": "Semakan manusia", "Data preview": "Pratonton data", "Delete dataset version?": "Padam versi set data?", "Save changes": "Simpan perubahan", "Dataset version updated.": "Versi set data dikemas kini.", "Dataset version deleted.": "Versi set data dipadam.", "Preview unavailable.": "Pratonton tidak tersedia.", "How to use this workspace": "Cara menggunakan ruang kerja ini", "1. Add a model endpoint": "1. Tambah titik akhir model", "2. Register a dataset": "2. Daftar set data", "3. Download and verify": "3. Muat turun dan sahkan", "4. Create a prompt package": "4. Cipta pakej prom", "5. Queue a dataset run": "5. Letakkan larian set data dalam baris", "6. Inspect evidence": "6. Periksa bukti", "7. Judge, review, and report": "7. Nilai, semak dan lapor", "6 steps": "6 langkah", "4. Queue a dataset run": "4. Letakkan larian set data dalam baris", "5. Inspect evidence": "5. Periksa bukti", "6. Analyze results": "6. Analisis keputusan", "Runs": "Larian", "Datasets": "Set data", "Analysis": "Analisis", "Open Models": "Buka model", "Open Datasets": "Buka set data", "Review Datasets": "Semak set data", "Open Runs": "Buka larian", "Inspect Runs": "Periksa larian", "Open Analysis": "Buka analisis", "Selected model endpoint": "Titik akhir model yang dipilih", "Select a configured endpoint to inspect it.": "Pilih titik akhir yang dikonfigurasikan untuk memeriksanya.", "Register a source, then prepare, validate, and inspect it here.": "Daftar sumber, kemudian sediakan, sahkan dan periksa di sini.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.": "Pilih larian daripada inventori larian untuk membuka ringkasan, bukti dan sejarah kitar hayatnya.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.": "Siasat bukti kualiti, kebolehpercayaan, latensi, kos dan bukti antara larian yang dibekalkan.", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.": "Setiap peringkat membuka destinasi penilaian penting, jadi panduan kekal sebagai laluan boleh laksana dan bukan senarai semak statik.", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.": "Larian · pilih set data, metrik penilaian, medan rujukan dan titik akhir, kemudian letakkan larian dalam baris.", "Runs · open the run to review samples, scores, latency, cost, and errors.": "Larian · buka larian untuk menyemak sampel, skor, latensi, kos dan ralat.", "Analysis · inspect evaluation dimensions or compare two completed runs.": "Analisis · periksa dimensi penilaian atau bandingkan dua larian yang telah selesai.", "Filter benchmarks": "Tapis penanda aras", "Find run": "Cari larian", "Run status": "Status larian", "No runs match the current filters.": "Tiada larian sepadan dengan penapis semasa.", "Pause download": "Jeda muat turun", "Validate cache": "Sahkan cache", "Clear cache": "Kosongkan cache", "Retry download": "Cuba muat turun semula", "Upload local revision": "Muat naik semakan tempatan", "Benchmark composition": "Komposisi penanda aras", "Queue suite": "Letakkan set dalam baris", "Uses each selected endpoint’s saved connection and capacity configuration.": "Menggunakan sambungan dan konfigurasi kapasiti tersimpan setiap titik akhir yang dipilih.", "No available endpoints are ready to receive this suite.": "Tiada titik akhir tersedia yang bersedia menerima set ini.", "Loading disk usage…": "Memuatkan penggunaan cakera…", "No events available.": "Tiada peristiwa tersedia.", "Comparing…": "Membandingkan…", "registered versions": "versi berdaftar", "tasks visible": "tugas kelihatan", },
};

const redesignedWorkspacePhrases: Record<Locale, Record<string, string>> = {
  en: {},
  "zh-CN": {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "注册端点、验证连接，并让新运行的默认设置贴近其所管理的模型。",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "每个阶段都会打开现有的工作区目标，因此指南仍是一条可执行的路径，而非静态清单。",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "筛选条件仅影响此清单；加载的目录中仍可使用注册表记录及其操作控件。",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "监控排队工作、优先处理符合条件的任务，并将每项任务追溯到其不可变运行。",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "生成可移植的评测工件，然后管理其受控的只读共享策略。",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "连接、速率限制和成本设置仍可编辑，同时不会暴露已存储的凭据。",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "这些默认值会合并到新排队的基准测试运行中，而不会更改已保存的端点。",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "将检测到的能力证据与运行兼容性检查所用的声明分开查看。",
    "No endpoints available": "没有可用端点",
    "Choose an endpoint to inspect its detection and declaration evidence.": "选择一个端点以检查其检测和声明证据。",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "查看版本化基准测试包、其支持的模态以及新运行使用的可用性状态。",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "管理源版本、缓存数据、许可证和字段映射，同时始终查看所选数据集的证据。",
    "No dataset versions": "没有数据集版本",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "从工作区目录注册数据集源，然后返回此处准备、验证并检查它。",
    "Dataset inventory": "数据集清单",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "选择一个源版本以检查其缓存、元数据和生命周期操作。",
    "Open suite builder": "打开套件构建器",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "组合版本化基准测试集并将其加入已就绪端点的队列，同时保留每个套件背后的基准测试证据。",
    "No evaluation suites": "没有评测套件",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "从工作区目录创建套件，以定义版本化基准测试组合和默认执行设置。",
    "Suite inventory": "套件清单",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "选择一个版本化套件以检查组合并将其加入可用端点队列。",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "构建版本化输入、附加已验证媒体、组合套件，并在不离开设置的情况下检查目录。",
    "4 workbench modes": "4 种工作台模式",
    "Run inventory": "运行清单",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "选择一个快照以检查生命周期证据和可导出的工件。",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "启动不可变的评测快照，然后检查其运行和证据轨迹。",
    "Queue dataset evaluation": "将数据集评测加入队列",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "为新评测选择可用数据集、提示版本和端点。",
    "Selected run inspector": "所选运行检查器",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "从持久清单选择一个运行以打开其摘要、证据和生命周期历史。",
    "Queue inventory": "队列清单",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "虚拟化行可让高容量队列保持响应，同时保留任务级运行控件。",
    "Find task": "查找任务",
    "Task status": "任务状态",
    "No tasks match the current filters.": "没有任务符合当前筛选条件。",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "跟踪活动任务租约以及当前执行评测工作的工作器容量。",
    "No active worker leases": "没有活动工作器租约",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "当前没有工作器有活动租约。在更改部署容量前，请检查队列和系统运行状况。",
    "Open task queue": "打开任务队列",
    "Active leases": "活动租约",
    "Connected workers": "已连接工作器",
    "Tasks currently leased or running": "当前已租赁或运行的任务",
    "Distinct workers with an active lease": "有活动租约的不同工作器",
    "Pending tasks reported by system health": "系统运行状况报告的待处理任务",
    "Health signal unavailable": "运行状况信号不可用",
    "Active worker leases": "活动工作器租约",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "每项任务都会记录租约到期时间，因此可以诊断停滞的工作器而无需更改队列状态。",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "调查各评测维度中提供的质量、可靠性、延迟和成本证据。",
    "Loading analysis": "正在加载分析",
    "Analysis matrix": "分析矩阵",
    "The analysis matrix is loading from the evaluation service.": "正在从评测服务加载分析矩阵。",
    "Analysis context": "分析上下文",
    "The selected baseline applies to every evidence cell and delta shown below.": "所选基准线适用于下方显示的每个证据单元格和差值。",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "单击条形图或按 Enter 键以检查提供的模型能力结果。",
    "Compare runs": "比较运行",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "比较同一基准测试版本的两个已完成运行，并保留完整的证据轨迹。",
    "Comparison sources": "比较来源",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "选择两个不同的已完成快照。差异始终按运行 A 减去运行 B 计算。",
    "Comparison evidence": "比较证据",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "选择两个源运行并进行比较，以显示共享样本结果和指标差异。",
    "Choose two completed runs to begin an evidence-backed comparison.": "选择两个已完成运行以开始有证据支持的比较。",
    "Report context": "报告上下文",
    "Select the run whose immutable evidence snapshot should anchor this report.": "选择其不可变证据快照应作为本报告基础的运行。",
    "Report source run": "报告源运行",
    "Select a report source": "选择报告源",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "选择上方的评测运行以生成和管理其工件，而无需返回单独页面。",
    "Select a run to generate a portable report or inspect saved artifacts.": "选择一个运行以生成可移植报告或检查已保存的工件。",
    "Generate report": "生成报告",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "选择报告形式，然后生成下一次审核或交接所需的下载格式。",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "下载已生成的工件，或创建带有明确证据和下载控件的受限共享链接。",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "使人工评分和评审判断与正在审核的精确运行快照和样本保持关联。",
    "Select an evidence sample": "选择证据样本",
    "Review context": "审核上下文",
  },
  fr: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "Enregistrez les points de terminaison, validez la connectivité et conservez les paramètres par défaut des nouvelles exécutions près des modèles qu’ils régissent.",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "Chaque étape ouvre la destination existante de l’espace de travail, de sorte que le guide reste un parcours actionnable plutôt qu’une liste statique.",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "Les filtres n’affectent que cet inventaire ; les entrées du registre et leurs contrôles opérationnels restent disponibles dans le catalogue chargé.",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "Surveillez le travail en file d’attente, priorisez les tâches éligibles et rattachez chacune à son exécution immuable.",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "Générez des artefacts d’évaluation portables, puis gérez leurs politiques de partage contrôlées en lecture seule.",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "Les paramètres de connexion, de limite de débit et de coût restent modifiables sans exposer les identifiants stockés.",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "Ces valeurs par défaut sont fusionnées dans une nouvelle exécution de benchmark mise en file sans modifier un point de terminaison enregistré.",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "Examinez séparément les preuves de capacités détectées et les déclarations utilisées par les vérifications de compatibilité des exécutions.",
    "No endpoints available": "Aucun point de terminaison disponible",
    "Choose an endpoint to inspect its detection and declaration evidence.": "Choisissez un point de terminaison pour examiner ses preuves de détection et de déclaration.",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "Examinez les packs de benchmark versionnés, leurs modalités prises en charge et l’état de disponibilité utilisé par les nouvelles exécutions.",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "Gérez les versions sources, les données en cache, les licences et le mappage des champs tout en gardant les preuves du jeu de données sélectionné visibles.",
    "No dataset versions": "Aucune version de jeu de données",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "Enregistrez une source de jeu de données depuis le catalogue de l’espace de travail, puis revenez ici pour la préparer, la valider et l’examiner.",
    "Dataset inventory": "Inventaire des jeux de données",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "Sélectionnez une version source pour examiner son cache, ses métadonnées et ses actions de cycle de vie.",
    "Open suite builder": "Ouvrir le générateur de suites",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "Composez des ensembles de benchmarks versionnés et mettez-les en file sur des points de terminaison prêts sans perdre les preuves de benchmark associées à chaque suite.",
    "No evaluation suites": "Aucune suite d’évaluation",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "Créez une suite depuis le catalogue de l’espace de travail pour définir la composition de benchmarks versionnée et les paramètres d’exécution par défaut.",
    "Suite inventory": "Inventaire des suites",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "Choisissez une suite versionnée pour examiner sa composition et la mettre en file sur un point de terminaison disponible.",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "Créez des entrées versionnées, joignez des médias validés, composez des suites et examinez le catalogue sans quitter la configuration.",
    "4 workbench modes": "4 modes d’atelier",
    "Run inventory": "Inventaire des exécutions",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "Sélectionnez un instantané pour examiner les preuves de cycle de vie et les artefacts exportables.",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "Lancez des instantanés d’évaluation immuables, puis examinez leurs traces opérationnelles et de preuve.",
    "Queue dataset evaluation": "Mettre l’évaluation du jeu de données en file",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "Choisissez un jeu de données, une version de prompt et un point de terminaison disponibles pour une nouvelle évaluation.",
    "Selected run inspector": "Inspecteur de l’exécution sélectionnée",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "Sélectionnez une exécution dans l’inventaire persistant pour ouvrir son résumé, ses preuves et son historique de cycle de vie.",
    "Queue inventory": "Inventaire de la file",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "Les lignes virtualisées gardent les files à fort volume réactives tout en conservant les contrôles opérationnels au niveau des tâches.",
    "Find task": "Rechercher une tâche",
    "Task status": "État de la tâche",
    "No tasks match the current filters.": "Aucune tâche ne correspond aux filtres actuels.",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "Suivez les baux de tâches actifs et la capacité des agents qui effectuent actuellement le travail d’évaluation.",
    "No active worker leases": "Aucun bail d’agent actif",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "Aucun agent n’a de bail actif pour le moment. Examinez la file et l’état du système avant de modifier la capacité de déploiement.",
    "Open task queue": "Ouvrir la file des tâches",
    "Active leases": "Baux actifs",
    "Connected workers": "Agents connectés",
    "Tasks currently leased or running": "Tâches actuellement louées ou en cours",
    "Distinct workers with an active lease": "Agents distincts avec un bail actif",
    "Pending tasks reported by system health": "Tâches en attente signalées par l’état du système",
    "Health signal unavailable": "Signal d’état indisponible",
    "Active worker leases": "Baux d’agents actifs",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "L’expiration du bail est enregistrée avec chaque tâche afin que les agents bloqués puissent être diagnostiqués sans modifier l’état de la file.",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "Examinez les preuves fournies de qualité, de fiabilité, de latence et de coût dans toutes les dimensions d’évaluation.",
    "Loading analysis": "Chargement de l’analyse",
    "Analysis matrix": "Matrice d’analyse",
    "The analysis matrix is loading from the evaluation service.": "La matrice d’analyse est en cours de chargement depuis le service d’évaluation.",
    "Analysis context": "Contexte d’analyse",
    "The selected baseline applies to every evidence cell and delta shown below.": "La référence sélectionnée s’applique à chaque cellule de preuve et à chaque écart affiché ci-dessous.",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "Cliquez sur une barre ou utilisez Entrée pour examiner le résultat de capacité du modèle fourni.",
    "Compare runs": "Comparer les exécutions",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "Comparez deux exécutions terminées de la même version de benchmark et conservez la piste complète des preuves.",
    "Comparison sources": "Sources de comparaison",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "Choisissez deux instantanés terminés distincts. Les différences sont toujours calculées comme l’exécution A moins l’exécution B.",
    "Comparison evidence": "Preuves de comparaison",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "Sélectionnez deux exécutions sources et comparez-les pour révéler les résultats d’échantillons partagés et les écarts de métriques.",
    "Choose two completed runs to begin an evidence-backed comparison.": "Choisissez deux exécutions terminées pour commencer une comparaison étayée par des preuves.",
    "Report context": "Contexte du rapport",
    "Select the run whose immutable evidence snapshot should anchor this report.": "Sélectionnez l’exécution dont l’instantané de preuve immuable doit servir de base à ce rapport.",
    "Report source run": "Exécution source du rapport",
    "Select a report source": "Sélectionner une source de rapport",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "Choisissez une exécution d’évaluation ci-dessus pour générer et gérer ses artefacts sans revenir à une page séparée.",
    "Select a run to generate a portable report or inspect saved artifacts.": "Sélectionnez une exécution pour générer un rapport portable ou examiner les artefacts enregistrés.",
    "Generate report": "Générer le rapport",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "Sélectionnez la forme du rapport, puis générez le format de téléchargement requis pour la prochaine révision ou transmission.",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "Téléchargez un artefact généré ou créez un lien de partage limité avec des contrôles explicites de preuve et de téléchargement.",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "Conservez les scores humains et les évaluations des juges liés à l’instantané précis d’exécution et à l’échantillon en cours d’examen.",
    "Select an evidence sample": "Sélectionner un échantillon de preuve",
    "Review context": "Contexte d’examen",
  },
  de: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "Registrieren Sie Endpunkte, prüfen Sie die Verbindung und halten Sie die Standardwerte für neue Ausführungen bei den Modellen, für die sie gelten.",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "Jede Phase öffnet das vorhandene Arbeitsbereichsziel, sodass der Leitfaden ein umsetzbarer Ablauf statt einer statischen Checkliste bleibt.",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "Filter wirken sich nur auf diese Übersicht aus; Registereinträge und deren Betriebssteuerungen bleiben im geladenen Katalog verfügbar.",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "Überwachen Sie die wartende Arbeit, priorisieren Sie berechtigte Aufgaben und verfolgen Sie jede Aufgabe zu ihrem unveränderlichen Lauf zurück.",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "Erzeugen Sie portable Evaluierungsartefakte und verwalten Sie anschließend deren kontrollierte schreibgeschützte Freigaberichtlinien.",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "Verbindungs-, Ratenbegrenzungs- und Kosteneinstellungen bleiben bearbeitbar, ohne gespeicherte Anmeldedaten offenzulegen.",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "Diese Standardwerte werden in eine neu eingereihte Benchmark-Ausführung übernommen, ohne einen gespeicherten Endpunkt zu ändern.",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "Prüfen Sie erkannte Fähigkeitsnachweise getrennt von den Deklarationen, die von Kompatibilitätsprüfungen für Ausführungen verwendet werden.",
    "No endpoints available": "Keine Endpunkte verfügbar",
    "Choose an endpoint to inspect its detection and declaration evidence.": "Wählen Sie einen Endpunkt aus, um dessen Erkennungs- und Deklarationsnachweise zu prüfen.",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "Prüfen Sie versionierte Benchmark-Pakete, ihre unterstützten Modalitäten und den Verfügbarkeitsstatus, der für neue Ausführungen verwendet wird.",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "Verwalten Sie Quellversionen, zwischengespeicherte Daten, Lizenzen und Feldzuordnungen, während die Nachweise des ausgewählten Datensatzes sichtbar bleiben.",
    "No dataset versions": "Keine Datensatzversionen",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "Registrieren Sie eine Datensatzquelle aus dem Arbeitsbereichskatalog und kehren Sie anschließend hierher zurück, um sie vorzubereiten, zu validieren und zu prüfen.",
    "Dataset inventory": "Datensatzübersicht",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "Wählen Sie eine Quellversion aus, um deren Cache, Metadaten und Lebenszyklusaktionen zu prüfen.",
    "Open suite builder": "Suite-Builder öffnen",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "Stellen Sie versionierte Benchmark-Sets zusammen und reihen Sie sie bei bereiten Endpunkten ein, ohne die Benchmark-Nachweise hinter jeder Suite zu verlieren.",
    "No evaluation suites": "Keine Bewertungssuiten",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "Erstellen Sie eine Suite aus dem Arbeitsbereichskatalog, um die versionierte Benchmark-Zusammenstellung und Standardausführungseinstellungen festzulegen.",
    "Suite inventory": "Suite-Übersicht",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "Wählen Sie eine versionierte Suite aus, um ihre Zusammensetzung zu prüfen und sie bei einem verfügbaren Endpunkt einzureihen.",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "Erstellen Sie versionierte Eingaben, fügen Sie validierte Medien an, stellen Sie Suiten zusammen und prüfen Sie den Katalog, ohne die Einrichtung zu verlassen.",
    "4 workbench modes": "4 Workbench-Modi",
    "Run inventory": "Ausführungsübersicht",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "Wählen Sie einen Snapshot aus, um Lebenszyklusnachweise und exportierbare Artefakte zu prüfen.",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "Starten Sie unveränderliche Evaluierungssnapshots und prüfen Sie anschließend deren Betriebs- und Nachweisspur.",
    "Queue dataset evaluation": "Datensatzevaluierung einreihen",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "Wählen Sie einen verfügbaren Datensatz, eine Prompt-Version und einen Endpunkt für eine neue Evaluierung aus.",
    "Selected run inspector": "Prüfer für ausgewählte Ausführung",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "Wählen Sie eine Ausführung aus der dauerhaften Übersicht aus, um ihre Zusammenfassung, Nachweise und Lebenszyklushistorie zu öffnen.",
    "Queue inventory": "Warteschlangenübersicht",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "Virtualisierte Zeilen halten Warteschlangen mit hohem Volumen reaktionsfähig und bewahren zugleich Betriebssteuerungen auf Aufgabenebene.",
    "Find task": "Aufgabe suchen",
    "Task status": "Aufgabenstatus",
    "No tasks match the current filters.": "Keine Aufgaben entsprechen den aktuellen Filtern.",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "Verfolgen Sie aktive Aufgaben-Leases und die Worker-Kapazität, die derzeit Evaluierungsarbeit ausführt.",
    "No active worker leases": "Keine aktiven Worker-Leases",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "Kein Worker hat derzeit ein aktives Lease. Prüfen Sie Warteschlange und Systemzustand, bevor Sie die Bereitstellungskapazität ändern.",
    "Open task queue": "Aufgabenwarteschlange öffnen",
    "Active leases": "Aktive Leases",
    "Connected workers": "Verbundene Worker",
    "Tasks currently leased or running": "Derzeit geleaste oder laufende Aufgaben",
    "Distinct workers with an active lease": "Unterschiedliche Worker mit aktivem Lease",
    "Pending tasks reported by system health": "Von der Systemgesundheit gemeldete ausstehende Aufgaben",
    "Health signal unavailable": "Zustandssignal nicht verfügbar",
    "Active worker leases": "Aktive Worker-Leases",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "Der Ablauf eines Leases wird mit jeder Aufgabe gespeichert, damit festgefahrene Worker diagnostiziert werden können, ohne den Warteschlangenzustand zu ändern.",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "Untersuchen Sie die bereitgestellten Qualitäts-, Zuverlässigkeits-, Latenz- und Kostennachweise über alle Evaluierungsdimensionen hinweg.",
    "Loading analysis": "Analyse wird geladen",
    "Analysis matrix": "Analysematrix",
    "The analysis matrix is loading from the evaluation service.": "Die Analysematrix wird vom Evaluierungsdienst geladen.",
    "Analysis context": "Analysekontext",
    "The selected baseline applies to every evidence cell and delta shown below.": "Die ausgewählte Basislinie gilt für jede unten dargestellte Nachweiszelle und Differenz.",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "Klicken Sie auf einen Balken oder verwenden Sie die Eingabetaste, um das bereitgestellte Modellfähigkeits-Ergebnis zu prüfen.",
    "Compare runs": "Ausführungen vergleichen",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "Vergleichen Sie zwei abgeschlossene Ausführungen derselben Benchmark-Version und bewahren Sie die vollständige Nachweisspur auf.",
    "Comparison sources": "Vergleichsquellen",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "Wählen Sie zwei unterschiedliche abgeschlossene Snapshots. Unterschiede werden immer als Ausführung A minus Ausführung B berechnet.",
    "Comparison evidence": "Vergleichsnachweise",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "Wählen Sie zwei Quellausführungen aus und vergleichen Sie sie, um Ergebnisse gemeinsamer Stichproben und Metrikdifferenzen offenzulegen.",
    "Choose two completed runs to begin an evidence-backed comparison.": "Wählen Sie zwei abgeschlossene Ausführungen, um einen nachweisgestützten Vergleich zu beginnen.",
    "Report context": "Berichtskontext",
    "Select the run whose immutable evidence snapshot should anchor this report.": "Wählen Sie die Ausführung aus, deren unveränderlicher Nachweis-Snapshot diesen Bericht verankern soll.",
    "Report source run": "Berichtsquellausführung",
    "Select a report source": "Berichtsquelle auswählen",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "Wählen Sie oben eine Evaluierungsausführung aus, um ihre Artefakte zu erzeugen und zu verwalten, ohne zu einer separaten Seite zurückzukehren.",
    "Select a run to generate a portable report or inspect saved artifacts.": "Wählen Sie eine Ausführung aus, um einen portablen Bericht zu erzeugen oder gespeicherte Artefakte zu prüfen.",
    "Generate report": "Bericht erstellen",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "Wählen Sie die Berichtsform und erzeugen Sie anschließend das für die nächste Überprüfung oder Übergabe benötigte Downloadformat.",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "Laden Sie ein erzeugtes Artefakt herunter oder erstellen Sie einen begrenzten Freigabelink mit expliziten Nachweis- und Download-Steuerungen.",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "Halten Sie menschliche Bewertungen und Gutachterbeurteilungen an den genauen Ausführungs-Snapshot und die geprüfte Stichprobe gebunden.",
    "Select an evidence sample": "Nachweisstichprobe auswählen",
    "Review context": "Prüfungskontext",
  },
  ru: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "Зарегистрируйте конечные точки, проверьте подключение и храните параметры по умолчанию для новых запусков рядом с моделями, которыми они управляют.",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "Каждый этап открывает существующий раздел рабочего пространства, поэтому руководство остаётся практическим маршрутом, а не статическим контрольным списком.",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "Фильтры влияют только на этот перечень; записи реестра и их рабочие элементы управления остаются доступными в загруженном каталоге.",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "Отслеживайте работу в очереди, расставляйте приоритеты для подходящих задач и прослеживайте каждую задачу до её неизменяемого запуска.",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "Создавайте переносимые артефакты оценки, а затем управляйте их контролируемыми политиками общего доступа только для чтения.",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "Параметры подключения, ограничения частоты и стоимости можно изменять без раскрытия сохранённых учётных данных.",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "Эти значения по умолчанию объединяются с новым поставленным в очередь запуском бенчмарка без изменения сохранённой конечной точки.",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "Изучайте обнаруженные доказательства возможностей отдельно от деклараций, используемых проверками совместимости запусков.",
    "No endpoints available": "Нет доступных конечных точек",
    "Choose an endpoint to inspect its detection and declaration evidence.": "Выберите конечную точку, чтобы изучить доказательства её обнаружения и декларации.",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "Изучайте версионированные пакеты бенчмарков, поддерживаемые ими модальности и состояние доступности, используемое новыми запусками.",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "Управляйте версиями источников, кэшированными данными, лицензиями и сопоставлением полей, сохраняя на виду доказательства выбранного набора данных.",
    "No dataset versions": "Нет версий набора данных",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "Зарегистрируйте источник набора данных из каталога рабочего пространства, затем вернитесь сюда, чтобы подготовить, проверить и изучить его.",
    "Dataset inventory": "Инвентарь наборов данных",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "Выберите версию источника, чтобы изучить её кэш, метаданные и действия жизненного цикла.",
    "Open suite builder": "Открыть конструктор наборов",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "Собирайте версионированные наборы бенчмарков и ставьте их в очередь на готовых конечных точках, не теряя доказательства бенчмарка для каждого набора.",
    "No evaluation suites": "Нет наборов оценки",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "Создайте набор из каталога рабочего пространства, чтобы определить версионированный состав бенчмарков и параметры выполнения по умолчанию.",
    "Suite inventory": "Инвентарь наборов",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "Выберите версионированный набор, чтобы изучить состав и поставить его в очередь на доступной конечной точке.",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "Создавайте версионированные входные данные, прикрепляйте проверенные медиафайлы, составляйте наборы и изучайте каталог, не покидая настройку.",
    "4 workbench modes": "4 режима рабочей области",
    "Run inventory": "Инвентарь запусков",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "Выберите снимок, чтобы изучить доказательства жизненного цикла и экспортируемые артефакты.",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "Запускайте неизменяемые снимки оценки, затем изучайте их рабочий журнал и след доказательств.",
    "Queue dataset evaluation": "Поставить оценку набора данных в очередь",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "Выберите доступный набор данных, версию промпта и конечную точку для новой оценки.",
    "Selected run inspector": "Проверка выбранного запуска",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "Выберите запуск из постоянного списка, чтобы открыть его сводку, доказательства и историю жизненного цикла.",
    "Queue inventory": "Инвентарь очереди",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "Виртуализированные строки сохраняют отзывчивость очередей большого объёма, сохраняя операционные элементы управления на уровне задач.",
    "Find task": "Найти задачу",
    "Task status": "Статус задачи",
    "No tasks match the current filters.": "Нет задач, соответствующих текущим фильтрам.",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "Отслеживайте активные аренды задач и ресурсы работников, которые сейчас выполняют оценочную работу.",
    "No active worker leases": "Нет активных аренд работников",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "Сейчас ни у одного работника нет активной аренды. Проверьте очередь и состояние системы перед изменением мощности развёртывания.",
    "Open task queue": "Открыть очередь задач",
    "Active leases": "Активные аренды",
    "Connected workers": "Подключённые работники",
    "Tasks currently leased or running": "Задачи, которые сейчас арендованы или выполняются",
    "Distinct workers with an active lease": "Отдельные работники с активной арендой",
    "Pending tasks reported by system health": "Ожидающие задачи, о которых сообщает состояние системы",
    "Health signal unavailable": "Сигнал состояния недоступен",
    "Active worker leases": "Активные аренды работников",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "Срок аренды записывается для каждой задачи, чтобы можно было диагностировать зависших работников без изменения состояния очереди.",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "Исследуйте предоставленные доказательства качества, надёжности, задержки и стоимости по всем измерениям оценки.",
    "Loading analysis": "Загрузка анализа",
    "Analysis matrix": "Матрица анализа",
    "The analysis matrix is loading from the evaluation service.": "Матрица анализа загружается из сервиса оценки.",
    "Analysis context": "Контекст анализа",
    "The selected baseline applies to every evidence cell and delta shown below.": "Выбранная базовая линия применяется к каждой ячейке доказательств и разнице, показанной ниже.",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "Щёлкните по полосе или нажмите Enter, чтобы изучить предоставленный результат возможностей модели.",
    "Compare runs": "Сравнить запуски",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "Сравните два завершённых запуска одной версии бенчмарка и сохраните полную цепочку доказательств.",
    "Comparison sources": "Источники сравнения",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "Выберите два разных завершённых снимка. Разницы всегда рассчитываются как запуск A минус запуск B.",
    "Comparison evidence": "Доказательства сравнения",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "Выберите два исходных запуска и сравните их, чтобы показать результаты общих образцов и различия метрик.",
    "Choose two completed runs to begin an evidence-backed comparison.": "Выберите два завершённых запуска, чтобы начать сравнение, подкреплённое доказательствами.",
    "Report context": "Контекст отчёта",
    "Select the run whose immutable evidence snapshot should anchor this report.": "Выберите запуск, чей неизменяемый снимок доказательств должен служить основой для этого отчёта.",
    "Report source run": "Исходный запуск отчёта",
    "Select a report source": "Выберите источник отчёта",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "Выберите запуск оценки выше, чтобы создавать и управлять его артефактами, не возвращаясь на отдельную страницу.",
    "Select a run to generate a portable report or inspect saved artifacts.": "Выберите запуск, чтобы создать переносимый отчёт или изучить сохранённые артефакты.",
    "Generate report": "Создать отчёт",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "Выберите форму отчёта, затем создайте формат загрузки, необходимый для следующей проверки или передачи.",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "Скачайте созданный артефакт или создайте ограниченную ссылку общего доступа с явными элементами управления доказательствами и загрузкой.",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "Сохраняйте связь оценок людей и оценок судей с точным снимком запуска и проверяемым образцом.",
    "Select an evidence sample": "Выберите образец доказательств",
    "Review context": "Контекст проверки",
  },
  ja: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "エンドポイントを登録して接続を検証し、新しい実行の既定値を対象モデルの近くに保ちます。",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "各段階で既存のワークスペース画面を開くため、このガイドは静的なチェックリストではなく実行可能な手順として機能します。",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "フィルターはこの一覧にのみ影響します。レジストリの記録とその運用コントロールは、読み込まれたカタログで引き続き利用できます。",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "キューに入った作業を監視し、対象のタスクに優先順位を付け、各タスクを不変の実行まで追跡します。",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "ポータブルな評価アーティファクトを生成し、その後、制御された読み取り専用の共有ポリシーを管理します。",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "接続、レート制限、コストの設定は、保存済みの認証情報を公開せずに編集できます。",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "これらの既定値は、保存済みエンドポイントを変更せずに、新たにキューに入れたベンチマーク実行にマージされます。",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "検出された機能の証拠を、実行の互換性チェックで使用する宣言とは分けて確認します。",
    "No endpoints available": "利用可能なエンドポイントはありません",
    "Choose an endpoint to inspect its detection and declaration evidence.": "エンドポイントを選択して、その検出および宣言の証拠を確認します。",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "バージョン管理されたベンチマークパック、対応モダリティ、および新しい実行で使用される可用性状態を確認します。",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "ソースのバージョン、キャッシュデータ、ライセンス、フィールドマッピングを管理しながら、選択したデータセットの証拠を表示し続けます。",
    "No dataset versions": "データセットのバージョンはありません",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "ワークスペースカタログからデータセットソースを登録し、ここに戻って準備、検証、確認します。",
    "Dataset inventory": "データセット一覧",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "ソースバージョンを選択して、そのキャッシュ、メタデータ、ライフサイクル操作を確認します。",
    "Open suite builder": "スイートビルダーを開く",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "バージョン管理されたベンチマークセットを構成し、各スイートのベンチマーク証拠を失わずに準備済みエンドポイントでキューに入れます。",
    "No evaluation suites": "評価スイートはありません",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "ワークスペースカタログからスイートを作成し、バージョン管理されたベンチマーク構成と既定の実行設定を定義します。",
    "Suite inventory": "スイート一覧",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "バージョン管理されたスイートを選択して構成を確認し、利用可能なエンドポイントでキューに入れます。",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "バージョン管理された入力を作成し、検証済みメディアを添付し、スイートを構成して、設定画面を離れずにカタログを確認します。",
    "4 workbench modes": "4 つのワークベンチモード",
    "Run inventory": "実行一覧",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "スナップショットを選択して、ライフサイクルの証拠とエクスポート可能なアーティファクトを確認します。",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "不変の評価スナップショットを起動し、その運用と証拠の履歴を確認します。",
    "Queue dataset evaluation": "データセット評価をキューに追加",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "新しい評価のために、利用可能なデータセット、プロンプトバージョン、エンドポイントを選択します。",
    "Selected run inspector": "選択した実行のインスペクター",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "永続的な一覧から実行を選択して、概要、証拠、ライフサイクル履歴を開きます。",
    "Queue inventory": "キュー一覧",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "仮想化された行により、大量のキューでも応答性を保ちながらタスクレベルの運用コントロールを維持します。",
    "Find task": "タスクを検索",
    "Task status": "タスクの状態",
    "No tasks match the current filters.": "現在のフィルターに一致するタスクはありません。",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "アクティブなタスクリースと、現在評価作業を処理しているワーカー容量を追跡します。",
    "No active worker leases": "アクティブなワーカーリースはありません",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "現時点ではアクティブなリースを持つワーカーはいません。デプロイ容量を変更する前に、キューとシステムの健全性を確認してください。",
    "Open task queue": "タスクキューを開く",
    "Active leases": "アクティブなリース",
    "Connected workers": "接続されたワーカー",
    "Tasks currently leased or running": "現在リース中または実行中のタスク",
    "Distinct workers with an active lease": "アクティブなリースを持つ個別ワーカー",
    "Pending tasks reported by system health": "システムの健全性が報告した保留中のタスク",
    "Health signal unavailable": "健全性シグナルを利用できません",
    "Active worker leases": "アクティブなワーカーリース",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "各タスクにはリース期限が記録されるため、キューの状態を変更せずに停止したワーカーを診断できます。",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "評価の各次元で提供された品質、信頼性、レイテンシ、コストの証拠を調査します。",
    "Loading analysis": "分析を読み込み中",
    "Analysis matrix": "分析マトリクス",
    "The analysis matrix is loading from the evaluation service.": "分析マトリクスを評価サービスから読み込んでいます。",
    "Analysis context": "分析コンテキスト",
    "The selected baseline applies to every evidence cell and delta shown below.": "選択したベースラインは、以下に示すすべての証拠セルと差分に適用されます。",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "バーをクリックするか Enter キーを使用して、提供されたモデル機能の結果を確認します。",
    "Compare runs": "実行を比較",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "同じベンチマークバージョンの完了済み実行を 2 つ比較し、完全な証拠の履歴を保持します。",
    "Comparison sources": "比較ソース",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "異なる完了済みスナップショットを 2 つ選択します。差分は常に実行 A から実行 B を引いて計算されます。",
    "Comparison evidence": "比較の証拠",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "2 つのソース実行を選択して比較し、共有サンプルの結果とメトリクス差分を表示します。",
    "Choose two completed runs to begin an evidence-backed comparison.": "完了済みの実行を 2 つ選択して、証拠に基づく比較を開始します。",
    "Report context": "レポートコンテキスト",
    "Select the run whose immutable evidence snapshot should anchor this report.": "不変の証拠スナップショットをこのレポートの基準にする実行を選択します。",
    "Report source run": "レポートのソース実行",
    "Select a report source": "レポートのソースを選択",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "上の評価実行を選択して、別のページに戻らずにアーティファクトを生成・管理します。",
    "Select a run to generate a portable report or inspect saved artifacts.": "実行を選択して、ポータブルなレポートを生成するか、保存済みアーティファクトを確認します。",
    "Generate report": "レポートを生成",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "レポート形式を選択し、次のレビューまたは引き継ぎに必要なダウンロード形式を生成します。",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "生成されたアーティファクトをダウンロードするか、明示的な証拠とダウンロード制御を含む範囲指定の共有リンクを作成します。",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "人による採点と判定者の評価を、確認中の正確な実行スナップショットとサンプルに結び付けます。",
    "Select an evidence sample": "証拠サンプルを選択",
    "Review context": "レビューコンテキスト",
  },
  ko: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "엔드포인트를 등록하고 연결을 검증하며 새 실행의 기본값을 해당 모델 가까이에 유지합니다.",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "각 단계는 기존 작업 공간 대상을 열므로 가이드는 정적 체크리스트가 아니라 실행 가능한 경로로 유지됩니다.",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "필터는 이 인벤토리에만 적용되며 레지스트리 레코드와 운영 제어 기능은 로드된 카탈로그에서 계속 사용할 수 있습니다.",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "대기 중인 작업을 모니터링하고 적합한 작업의 우선순위를 정하며 각 작업을 불변 실행까지 추적합니다.",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "이식 가능한 평가 아티팩트를 생성한 다음 제어된 읽기 전용 공유 정책을 관리합니다.",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "연결, 속도 제한 및 비용 설정은 저장된 자격 증명을 노출하지 않고도 수정할 수 있습니다.",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "이러한 기본값은 저장된 엔드포인트를 변경하지 않고 새로 대기열에 넣은 벤치마크 실행에 병합됩니다.",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "감지된 기능 증거를 실행 호환성 검사에서 사용하는 선언과 별도로 확인합니다.",
    "No endpoints available": "사용 가능한 엔드포인트가 없습니다",
    "Choose an endpoint to inspect its detection and declaration evidence.": "탐지 및 선언 증거를 확인할 엔드포인트를 선택하세요.",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "버전이 지정된 벤치마크 팩, 지원되는 모달리티 및 새 실행에 사용되는 가용성 상태를 검토합니다.",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "소스 버전, 캐시된 데이터, 라이선스 및 필드 매핑을 관리하면서 선택한 데이터 세트의 증거를 계속 표시합니다.",
    "No dataset versions": "데이터 세트 버전이 없습니다",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "작업 공간 카탈로그에서 데이터 세트 소스를 등록한 다음 여기로 돌아와 준비, 검증 및 검토합니다.",
    "Dataset inventory": "데이터 세트 인벤토리",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "소스 버전을 선택하여 캐시, 메타데이터 및 수명 주기 작업을 검토합니다.",
    "Open suite builder": "스위트 빌더 열기",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "버전이 지정된 벤치마크 세트를 구성하고 각 스위트의 벤치마크 증거를 유지한 채 준비된 엔드포인트에서 대기열에 추가합니다.",
    "No evaluation suites": "평가 스위트가 없습니다",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "작업 공간 카탈로그에서 스위트를 만들어 버전이 지정된 벤치마크 구성과 기본 실행 설정을 정의합니다.",
    "Suite inventory": "스위트 인벤토리",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "버전이 지정된 스위트를 선택하여 구성을 검토하고 사용 가능한 엔드포인트에 대기열로 추가합니다.",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "버전이 지정된 입력을 만들고 검증된 미디어를 첨부하며 스위트를 구성하고 설정을 벗어나지 않고 카탈로그를 검토합니다.",
    "4 workbench modes": "4가지 워크벤치 모드",
    "Run inventory": "실행 인벤토리",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "스냅샷을 선택하여 수명 주기 증거와 내보낼 수 있는 아티팩트를 검토합니다.",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "불변 평가 스냅샷을 시작한 다음 운영 및 증거 추적을 검토합니다.",
    "Queue dataset evaluation": "데이터 세트 평가 대기열에 추가",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "새 평가에 사용할 수 있는 데이터 세트, 프롬프트 버전 및 엔드포인트를 선택하세요.",
    "Selected run inspector": "선택한 실행 검사기",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "영구 인벤토리에서 실행을 선택하여 요약, 증거 및 수명 주기 기록을 엽니다.",
    "Queue inventory": "대기열 인벤토리",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "가상화된 행은 대량 대기열의 응답성을 유지하면서 작업 수준 운영 제어를 보존합니다.",
    "Find task": "작업 찾기",
    "Task status": "작업 상태",
    "No tasks match the current filters.": "현재 필터와 일치하는 작업이 없습니다.",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "활성 작업 임대와 현재 평가 작업을 처리하는 워커 용량을 추적합니다.",
    "No active worker leases": "활성 워커 임대 없음",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "현재 활성 임대를 가진 작업자가 없습니다. 배포 용량을 변경하기 전에 대기열과 시스템 상태를 확인하세요.",
    "Open task queue": "작업 대기열 열기",
    "Active leases": "활성 임대",
    "Connected workers": "연결된 워커",
    "Tasks currently leased or running": "현재 임대되거나 실행 중인 작업",
    "Distinct workers with an active lease": "활성 임대를 가진 고유 워커",
    "Pending tasks reported by system health": "시스템 상태가 보고한 보류 작업",
    "Health signal unavailable": "상태 신호를 사용할 수 없음",
    "Active worker leases": "활성 워커 임대",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "각 작업에 임대 만료가 기록되므로 대기열 상태를 변경하지 않고 중단된 워커를 진단할 수 있습니다.",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "평가 차원 전반에서 제공된 품질, 안정성, 지연 시간 및 비용 증거를 조사합니다.",
    "Loading analysis": "분석 로드 중",
    "Analysis matrix": "분석 매트릭스",
    "The analysis matrix is loading from the evaluation service.": "평가 서비스에서 분석 매트릭스를 불러오는 중입니다.",
    "Analysis context": "분석 컨텍스트",
    "The selected baseline applies to every evidence cell and delta shown below.": "선택한 기준선은 아래에 표시된 모든 증거 셀과 델타에 적용됩니다.",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "막대를 클릭하거나 Enter 키를 사용하여 제공된 모델 기능 결과를 검토합니다.",
    "Compare runs": "실행 비교",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "동일한 벤치마크 버전의 완료된 두 실행을 비교하고 전체 증거 추적을 보존합니다.",
    "Comparison sources": "비교 소스",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "서로 다른 완료된 스냅샷 두 개를 선택하세요. 차이는 항상 실행 A에서 실행 B를 뺀 값으로 계산됩니다.",
    "Comparison evidence": "비교 증거",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "두 소스 실행을 선택하고 비교하여 공유 샘플 결과와 지표 델타를 확인합니다.",
    "Choose two completed runs to begin an evidence-backed comparison.": "증거 기반 비교를 시작할 완료된 실행 두 개를 선택하세요.",
    "Report context": "보고서 컨텍스트",
    "Select the run whose immutable evidence snapshot should anchor this report.": "불변 증거 스냅샷이 이 보고서의 기준이 될 실행을 선택하세요.",
    "Report source run": "보고서 소스 실행",
    "Select a report source": "보고서 소스 선택",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "위의 평가 실행을 선택하여 별도 페이지로 돌아가지 않고 아티팩트를 생성하고 관리합니다.",
    "Select a run to generate a portable report or inspect saved artifacts.": "실행을 선택하여 이식 가능한 보고서를 생성하거나 저장된 아티팩트를 검토합니다.",
    "Generate report": "보고서 생성",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "보고서 형식을 선택한 다음 다음 검토 또는 인계에 필요한 다운로드 형식을 생성합니다.",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "생성된 아티팩트를 다운로드하거나 명시적 증거 및 다운로드 제어가 있는 범위 지정 공유 링크를 만듭니다.",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "사람 점수와 심사자 평가를 검토 중인 정확한 실행 스냅샷 및 샘플에 연결합니다.",
    "Select an evidence sample": "증거 샘플 선택",
    "Review context": "검토 컨텍스트",
  },
  ms: {
    "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.": "Daftarkan titik akhir, sahkan sambungan dan kekalkan lalai larian baharu berdekatan model yang ditadbirnya.",
    "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.": "Setiap peringkat membuka destinasi ruang kerja sedia ada, jadi panduan kekal sebagai laluan boleh tindakan dan bukan senarai semak statik.",
    "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.": "Penapis hanya mempengaruhi inventori ini; rekod pendaftaran dan kawalan operasinya kekal tersedia dalam katalog yang dimuatkan.",
    "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.": "Pantau kerja beratur, utamakan tugas yang layak dan jejak setiap tugas kembali kepada larian tidak berubahnya.",
    "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.": "Jana artifak penilaian mudah alih, kemudian urus dasar perkongsian terkawal baca sahaja.",
    "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.": "Tetapan sambungan, had kadar dan kos kekal boleh diedit tanpa mendedahkan kelayakan yang disimpan.",
    "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.": "Lalai ini digabungkan ke dalam larian penanda aras yang baru dibariskan tanpa mengubah titik akhir tersimpan.",
    "Inspect detected capability evidence separately from the declarations used by run compatibility checks.": "Periksa bukti keupayaan dikesan secara berasingan daripada pengisytiharan yang digunakan oleh semakan keserasian larian.",
    "No endpoints available": "Tiada titik akhir tersedia",
    "Choose an endpoint to inspect its detection and declaration evidence.": "Pilih titik akhir untuk memeriksa bukti pengesanan dan pengisytiharannya.",
    "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.": "Periksa pakej penanda aras berversi, modaliti disokong dan status ketersediaan yang digunakan oleh larian baharu.",
    "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.": "Urus versi sumber, data cache, lesen dan pemetaan medan sambil mengekalkan bukti set data yang dipilih dalam paparan.",
    "No dataset versions": "Tiada versi set data",
    "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.": "Daftarkan sumber set data daripada katalog Ruang Kerja, kemudian kembali ke sini untuk menyedia, mengesahkan dan memeriksanya.",
    "Dataset inventory": "Inventori set data",
    "Select a source version to inspect its cache, metadata, and lifecycle actions.": "Pilih versi sumber untuk memeriksa cache, metadata dan tindakan kitar hayatnya.",
    "Open suite builder": "Buka pembina set",
    "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.": "Gubah set penanda aras berversi dan bariskan pada titik akhir sedia tanpa kehilangan bukti penanda aras di sebalik setiap set.",
    "No evaluation suites": "Tiada set penilaian",
    "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.": "Cipta set daripada katalog Ruang Kerja untuk mentakrifkan komposisi penanda aras berversi dan tetapan pelaksanaan lalai.",
    "Suite inventory": "Inventori set",
    "Choose a versioned suite to inspect composition and queue it on an available endpoint.": "Pilih set berversi untuk memeriksa komposisi dan bariskannya pada titik akhir yang tersedia.",
    "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.": "Bina input berversi, lampirkan media disahkan, gubah set dan periksa katalog tanpa meninggalkan persediaan.",
    "4 workbench modes": "4 mod meja kerja",
    "Run inventory": "Inventori larian",
    "Select a snapshot to inspect lifecycle evidence and exportable artifacts.": "Pilih petikan untuk memeriksa bukti kitar hayat dan artifak yang boleh dieksport.",
    "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.": "Lancarkan petikan penilaian tidak berubah, kemudian periksa jejak operasi dan buktinya.",
    "Queue dataset evaluation": "Letakkan penilaian set data dalam baris",
    "Choose an available dataset, prompt version, and endpoint for a new evaluation.": "Pilih set data, versi prom dan titik akhir yang tersedia untuk penilaian baharu.",
    "Selected run inspector": "Pemeriksa larian dipilih",
    "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.": "Pilih larian daripada inventori kekal untuk membuka ringkasan, bukti dan sejarah kitar hayatnya.",
    "Queue inventory": "Inventori baris",
    "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.": "Baris maya memastikan baris berjumlah tinggi responsif sambil mengekalkan kawalan operasi pada peringkat tugas.",
    "Find task": "Cari tugas",
    "Task status": "Status tugas",
    "No tasks match the current filters.": "Tiada tugas sepadan dengan penapis semasa.",
    "Track active task leases and the worker capacity currently consuming evaluation work.": "Jejaki pajakan tugas aktif dan kapasiti pekerja yang kini menjalankan kerja penilaian.",
    "No active worker leases": "Tiada pajakan pekerja aktif",
    "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.": "Tiada pekerja mempunyai pajakan aktif pada masa ini. Periksa baris dan kesihatan sistem sebelum mengubah kapasiti pelaksanaan.",
    "Open task queue": "Buka baris tugas",
    "Active leases": "Pajakan aktif",
    "Connected workers": "Pekerja bersambung",
    "Tasks currently leased or running": "Tugas yang kini dipajak atau berjalan",
    "Distinct workers with an active lease": "Pekerja berbeza dengan pajakan aktif",
    "Pending tasks reported by system health": "Tugas menunggu dilaporkan oleh kesihatan sistem",
    "Health signal unavailable": "Isyarat kesihatan tidak tersedia",
    "Active worker leases": "Pajakan pekerja aktif",
    "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.": "Tamat pajakan direkodkan bagi setiap tugas supaya pekerja terhenti boleh didiagnosis tanpa mengubah keadaan baris.",
    "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.": "Siasat bukti kualiti, kebolehpercayaan, kependaman dan kos yang dibekalkan merentas dimensi penilaian.",
    "Loading analysis": "Memuatkan analisis",
    "Analysis matrix": "Matriks analisis",
    "The analysis matrix is loading from the evaluation service.": "Matriks analisis sedang dimuatkan daripada perkhidmatan penilaian.",
    "Analysis context": "Konteks analisis",
    "The selected baseline applies to every evidence cell and delta shown below.": "Garis asas yang dipilih digunakan pada setiap sel bukti dan delta yang dipaparkan di bawah.",
    "Click or use Enter on a bar to inspect the supplied model-capability result.": "Klik bar atau gunakan Enter untuk memeriksa hasil keupayaan model yang dibekalkan.",
    "Compare runs": "Bandingkan larian",
    "Compare two completed runs from the same benchmark version and retain the complete evidence trail.": "Bandingkan dua larian selesai daripada versi penanda aras yang sama dan kekalkan jejak bukti lengkap.",
    "Comparison sources": "Sumber perbandingan",
    "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.": "Pilih dua petikan selesai yang berbeza. Perbezaan sentiasa dikira sebagai Larian A tolak Larian B.",
    "Comparison evidence": "Bukti perbandingan",
    "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.": "Pilih dua larian sumber dan bandingkannya untuk mendedahkan hasil sampel dikongsi serta delta metrik.",
    "Choose two completed runs to begin an evidence-backed comparison.": "Pilih dua larian selesai untuk memulakan perbandingan berasaskan bukti.",
    "Report context": "Konteks laporan",
    "Select the run whose immutable evidence snapshot should anchor this report.": "Pilih larian yang petikan bukti tidak berubahnya harus menjadi asas laporan ini.",
    "Report source run": "Larian sumber laporan",
    "Select a report source": "Pilih sumber laporan",
    "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.": "Pilih larian penilaian di atas untuk menjana dan mengurus artifaknya tanpa kembali ke halaman berasingan.",
    "Select a run to generate a portable report or inspect saved artifacts.": "Pilih larian untuk menjana laporan mudah alih atau memeriksa artifak disimpan.",
    "Generate report": "Jana laporan",
    "Select the report shape, then generate the download format needed by the next review or handoff.": "Pilih bentuk laporan, kemudian jana format muat turun yang diperlukan oleh semakan atau serahan seterusnya.",
    "Download a generated artifact or create a scoped share link with explicit evidence and download controls.": "Muat turun artifak dijana atau cipta pautan kongsi berskop dengan kawalan bukti dan muat turun yang jelas.",
    "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.": "Kekalkan pemarkahan manusia dan penilaian hakim terikat pada petikan larian serta sampel tepat yang sedang disemak.",
    "Select an evidence sample": "Pilih sampel bukti",
    "Review context": "Konteks semakan",
  },
};

const localizationCompletionPhrases: Record<Locale, Record<string, string>> = {
  en: {},
  "zh-CN": {
    "Endpoint inventory": "端点清单",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "在打开人工或独立评审工作流前，选择评测快照和样本。",
    "Review run": "审核运行",
    "Review sample": "审核样本",
    "Select a run to begin a human or judge review.": "选择一个运行以开始人工或评审模型审核。",
    "Human review workflow": "人工审核流程",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "配置受限的 API 用户，并将最近的管理活动与当前清单一同保留。",
    "User inventory": "用户清单",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "创建一个具有最低权限角色和可选并发上限的令牌账户。",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "在发放更多凭据前，角色、速率上限和状态仍清晰可见。",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "最新记录的管理变更会作为审计追踪保留，并与用户创建的值分开。",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "检查部署管理的配置、本地工作区偏好设置以及用于受保护服务调用的持有者令牌。",
    "Application and storage": "应用程序和存储",
    "Access and preferences": "访问和偏好设置",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "令牌只保留在此浏览器会话中。不再需要受保护访问时请将其清除。",
    "Operating guidance": "运行指南",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "选择与工作器拓扑匹配的存储部署，然后仅在此工作区使用主题切换。",
    "Name, source, status…": "名称、来源、状态…",
    "Benchmark, status, or ID": "基准、状态或 ID",
    "total runs": "运行总数",
  },
  fr: {
    "Endpoint inventory": "Inventaire des points de terminaison",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "Sélectionnez le snapshot d’évaluation et l’échantillon avant d’ouvrir les flux de révision humaine ou de juge indépendant.",
    "Review run": "Exécution à examiner",
    "Review sample": "Échantillon à examiner",
    "Select a run to begin a human or judge review.": "Sélectionnez une exécution pour commencer une révision humaine ou par juge.",
    "Human review workflow": "Flux de travail de révision humaine",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "Provisionnez des utilisateurs d’API restreints et conservez l’activité administrative récente avec l’inventaire actuel.",
    "User inventory": "Inventaire des utilisateurs",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "Créez un compte utilisant un jeton avec le rôle aux privilèges minimaux et un plafond de concurrence facultatif.",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "Les rôles, plafonds de débit et statuts restent visibles avant l’émission d’identifiants supplémentaires.",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "Les dernières modifications administratives enregistrées sont conservées comme piste d’audit, séparément des valeurs créées par les utilisateurs.",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "Examinez la configuration gérée par le déploiement, les préférences locales de l’espace de travail et le jeton porteur utilisé pour les appels de service protégés.",
    "Application and storage": "Application et stockage",
    "Access and preferences": "Accès et préférences",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "Le jeton ne reste que dans cette session de navigateur. Effacez-le lorsque vous n’avez plus besoin d’un accès protégé.",
    "Operating guidance": "Guide d’utilisation",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "Choisissez un déploiement de stockage adapté à la topologie des workers, puis utilisez le sélecteur de thème uniquement pour cet espace de travail.",
    "Name, source, status…": "Nom, source, statut…",
    "Benchmark, status, or ID": "Benchmark, statut ou identifiant",
    "total runs": "nombre total d’exécutions",
  },
  de: {
    "Endpoint inventory": "Endpunktübersicht",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "Wählen Sie den Bewertungsschnappschuss und die Stichprobe, bevor Sie Abläufe für menschliche oder unabhängige Bewertungen öffnen.",
    "Review run": "Zu prüfende Ausführung",
    "Review sample": "Zu prüfende Stichprobe",
    "Select a run to begin a human or judge review.": "Wählen Sie eine Ausführung, um eine menschliche oder Bewertungsprüfung zu beginnen.",
    "Human review workflow": "Arbeitsablauf für die menschliche Überprüfung",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "Stellen Sie eingeschränkte API-Benutzer bereit und behalten Sie die jüngsten Verwaltungsaktivitäten neben dem aktuellen Bestand im Blick.",
    "User inventory": "Benutzerübersicht",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "Erstellen Sie ein tokenbasiertes Konto mit der geringsten Berechtigung und einer optionalen Parallelitätsobergrenze.",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "Rollen, Ratenobergrenzen und Status bleiben sichtbar, bevor zusätzliche Anmeldedaten ausgegeben werden.",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "Die zuletzt erfassten Verwaltungsänderungen werden getrennt von benutzerdefinierten Werten als Prüfprotokoll aufbewahrt.",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "Prüfen Sie die vom Deployment verwaltete Konfiguration, lokale Arbeitsbereichseinstellungen und das Bearer-Token für geschützte Dienstaufrufe.",
    "Application and storage": "Anwendung und Speicher",
    "Access and preferences": "Zugriff und Einstellungen",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "Das Token bleibt nur in dieser Browsersitzung. Löschen Sie es, wenn Sie keinen geschützten Zugriff mehr benötigen.",
    "Operating guidance": "Betriebshinweise",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "Wählen Sie eine Speicherbereitstellung, die zur Worker-Topologie passt, und verwenden Sie den Designumschalter nur für diesen Arbeitsbereich.",
    "Name, source, status…": "Name, Quelle, Status…",
    "Benchmark, status, or ID": "Benchmark, Status oder ID",
    "total runs": "Ausführungen insgesamt",
  },
  ru: {
    "Endpoint inventory": "Реестр конечных точек",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "Выберите снимок оценки и образец, прежде чем открывать рабочие процессы проверки человеком или независимым судьёй.",
    "Review run": "Запуск для проверки",
    "Review sample": "Образец для проверки",
    "Select a run to begin a human or judge review.": "Выберите запуск, чтобы начать проверку человеком или судьёй.",
    "Human review workflow": "Процесс проверки человеком",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "Настраивайте ограниченных пользователей API и храните недавнюю административную активность рядом с текущим списком.",
    "User inventory": "Список пользователей",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "Создайте учётную запись с токеном, ролью с минимальными привилегиями и необязательным ограничением параллелизма.",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "Роли, ограничения частоты и статус остаются видимыми перед выпуском дополнительных учётных данных.",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "Последние зафиксированные административные изменения сохраняются как журнал аудита отдельно от значений, созданных пользователями.",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "Проверьте конфигурацию, управляемую развёртыванием, локальные настройки рабочего пространства и bearer-токен для защищённых вызовов службы.",
    "Application and storage": "Приложение и хранилище",
    "Access and preferences": "Доступ и настройки",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "Токен остаётся только в этом сеансе браузера. Очистите его, когда защищённый доступ больше не нужен.",
    "Operating guidance": "Руководство по эксплуатации",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "Выберите развёртывание хранилища, соответствующее топологии работников, затем используйте переключатель темы только для этого рабочего пространства.",
    "Name, source, status…": "Имя, источник, статус…",
    "Benchmark, status, or ID": "Бенчмарк, статус или идентификатор",
    "total runs": "всего запусков",
  },
  ja: {
    "Endpoint inventory": "エンドポイント一覧",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "人によるレビューまたは独立した判定者のワークフローを開く前に、評価スナップショットとサンプルを選択します。",
    "Review run": "レビュー対象の実行",
    "Review sample": "レビュー対象のサンプル",
    "Select a run to begin a human or judge review.": "人によるレビューまたは判定者のレビューを始める実行を選択します。",
    "Human review workflow": "人によるレビューのワークフロー",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "制限付き API ユーザーを準備し、最近の管理アクティビティを現在の一覧とともに保持します。",
    "User inventory": "ユーザー一覧",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "最小権限のロールと任意の同時実行上限を持つトークン対応アカウントを作成します。",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "追加の資格情報を発行する前に、ロール、レート上限、状態を確認できます。",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "最新の記録済み管理変更は、ユーザー作成値とは分けて監査証跡として保持されます。",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "デプロイメント管理の構成、ローカルのワークスペース設定、保護されたサービス呼び出しに使用するベアラートークンを確認します。",
    "Application and storage": "アプリケーションとストレージ",
    "Access and preferences": "アクセスと設定",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "トークンはこのブラウザ セッションにのみ保持されます。保護されたアクセスが不要になったら消去してください。",
    "Operating guidance": "運用ガイド",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "ワーカー構成に合ったストレージ デプロイメントを選び、このワークスペースにだけテーマ切り替えを使用します。",
    "Name, source, status…": "名前、ソース、状態…",
    "Benchmark, status, or ID": "ベンチマーク、ステータス、ID",
    "total runs": "実行総数",
  },
  ko: {
    "Endpoint inventory": "엔드포인트 인벤토리",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "사람 또는 독립 판정자 워크플로를 열기 전에 평가 스냅샷과 샘플을 선택하세요.",
    "Review run": "검토할 실행",
    "Review sample": "검토할 샘플",
    "Select a run to begin a human or judge review.": "사람 또는 판정자 검토를 시작할 실행을 선택하세요.",
    "Human review workflow": "사람 검토 워크플로",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "제한된 API 사용자를 구성하고 최근 관리 활동을 현재 인벤토리와 함께 유지하세요.",
    "User inventory": "사용자 인벤토리",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "최소 권한 역할과 선택적 동시 실행 상한을 가진 토큰 기반 계정을 만드세요.",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "추가 자격 증명을 발급하기 전에 역할, 속도 상한 및 상태가 계속 표시됩니다.",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "가장 최근에 기록된 관리 변경 사항은 사용자가 작성한 값과 별도로 감사 추적으로 보존됩니다.",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "배포가 관리하는 구성, 로컬 작업 공간 기본 설정 및 보호된 서비스 호출에 사용할 베어러 토큰을 확인하세요.",
    "Application and storage": "애플리케이션 및 스토리지",
    "Access and preferences": "액세스 및 기본 설정",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "토큰은 이 브라우저 세션에만 남아 있습니다. 보호된 액세스가 더 이상 필요하지 않으면 지우세요.",
    "Operating guidance": "운영 안내",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "작업자 토폴로지에 맞는 스토리지 배포를 선택한 다음 이 작업 공간에만 테마 전환을 사용하세요.",
    "Name, source, status…": "이름, 소스, 상태…",
    "Benchmark, status, or ID": "벤치마크, 상태 또는 ID",
    "total runs": "총 실행 수",
  },
  ms: {
    "Endpoint inventory": "Inventori titik akhir",
    "Choose the evaluation snapshot and sample before opening human or independent judge workflows.": "Pilih petikan penilaian dan sampel sebelum membuka aliran kerja semakan manusia atau hakim bebas.",
    "Review run": "Larian untuk disemak",
    "Review sample": "Sampel untuk disemak",
    "Select a run to begin a human or judge review.": "Pilih larian untuk memulakan semakan manusia atau hakim.",
    "Human review workflow": "Aliran kerja semakan manusia",
    "Provision constrained API users and keep recent administrative activity alongside the current inventory.": "Sediakan pengguna API terhad dan kekalkan aktiviti pentadbiran terkini bersama inventori semasa.",
    "User inventory": "Inventori pengguna",
    "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.": "Cipta akaun berasaskan token dengan peranan keistimewaan minimum dan had keserentakan pilihan.",
    "Roles, rate ceilings, and status remain visible before issuing additional credentials.": "Peranan, had kadar dan status kekal kelihatan sebelum kelayakan tambahan dikeluarkan.",
    "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.": "Perubahan pentadbiran terkini yang direkodkan dikekalkan sebagai jejak audit, berasingan daripada nilai yang dicipta pengguna.",
    "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.": "Periksa konfigurasi yang diurus penggunaan, keutamaan ruang kerja setempat dan token pembawa untuk panggilan perkhidmatan terlindung.",
    "Application and storage": "Aplikasi dan storan",
    "Access and preferences": "Akses dan keutamaan",
    "The token remains only in this browser session. Clear it when you no longer need protected access.": "Token kekal hanya dalam sesi pelayar ini. Kosongkannya apabila anda tidak lagi memerlukan akses terlindung.",
    "Operating guidance": "Panduan operasi",
    "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.": "Pilih penggunaan storan yang sepadan dengan topologi pekerja, kemudian gunakan togol tema untuk ruang kerja ini sahaja.",
    "Name, source, status…": "Nama, sumber, status…",
    "Benchmark, status, or ID": "Penanda aras, status atau ID",
    "total runs": "jumlah larian",
  },
};

const materializedStaticLabelPhrases: Record<Locale, Record<string, string>> = {
  "en": {
  },
  "zh-CN": {
    "Display name": "显示 名称",
    "Base URL": "基础 URL",
    "Model name": "模型 名称",
    "Protocol profile": "协议 配置文件",
    "API key": "API 密钥",
    "Custom headers (JSON)": "自定义 标头 (JSON)",
    "Endpoint concurrency": "端点 并发",
    "Shared API-key concurrency": "共享 API 密钥 并发",
    "Requests / minute": "请求 / 分钟",
    "Tokens / minute": "令牌 / 分钟",
    "Requests / second": "请求 / 秒",
    "Input tokens / minute": "输入 令牌 / 分钟",
    "Output tokens / minute": "输出 令牌 / 分钟",
    "Input / 1M tokens": "输入 / 1百万 令牌",
    "Output / 1M tokens": "输出 / 1百万 令牌",
    "Currency": "货币",
    "Tags (comma-separated)": "标签 (逗号分隔)",
    "Notes": "备注",
    "Saving...": "正在保存...",
    "Save encrypted endpoint": "保存 已加密 端点",
    "Benchmark pack": "基准 包",
    "Built-in benchmark prompt": "内置 基准 提示词",
    "Run concurrency cap": "运行 并发 上限",
    "Models": "模型",
    "Test connection": "测试 连接",
    "Probe capabilities": "探测 能力",
    "Queue selected benchmark": "队列 已选择 基准",
    "User: unknown": "用户: 未知",
    "User: supported": "用户: 受支持",
    "User: unsupported": "用户: 不支持",
    "Benchmarks": "基准",
    "Benchmark": "基准",
    "Version": "版本",
    "Source": "来源",
    "Status": "状态",
    "Modalities": "模态",
    "Operation": "操作",
    "Enable": "启用",
    "Disable": "禁用",
    "Managed by pack": "受管理 由 包",
    "Queue on": "队列 在",
    "Create prompt package": "创建 提示词 包",
    "Name": "名称",
    "Prompt type": "提示词 类型",
    "Official prompt": "官方 提示词",
    "Platform default": "平台 默认",
    "User custom": "用户 自定义",
    "Benchmark variant": "基准 变体",
    "Language-specific": "特定语言",
    "System message": "系统 消息",
    "User template": "用户 模板",
    "Output format (JSON)": "输出 格式 (JSON)",
    "Response parser (JSON)": "响应 解析器 (JSON)",
    "Scoring rule (JSON)": "评分 规则 (JSON)",
    "Change log": "更改 日志",
    "Save versioned prompt": "保存 已版本化 提示词",
    "Register dataset version": "注册 数据集 版本",
    "Dataset ID": "数据集 ID",
    "Revision": "修订",
    "Source HTTPS URL": "来源 HTTPS URL",
    "Expected SHA-256 checksum": "预期 SHA-256 校验和",
    "Credential binding ID": "凭据 绑定 ID",
    "License text": "许可证 文本",
    "Register dataset": "注册 数据集",
    "Preview": "预览",
    "Edit": "编辑",
    "Delete": "删除",
    "Cancel": "取消",
    "Endpoint": "端点",
    "Select available endpoint": "选择 可用 端点",
    "Sample ID": "样本 ID",
    "Prompt": "提示词",
    "Expected text answer": "预期 文本 答案",
    "Uploaded media": "已上传 媒体",
    "Queue multimodal run": "队列 多模态 运行",
    "Media asset upload": "媒体 资源 上传",
    "Create evaluation suite": "创建 评测 套件",
    "Benchmarks (id@version)": "基准 (ID@版本)",
    "Prompt overrides (JSON)": "提示词 覆盖 (JSON)",
    "Weight configuration (JSON)": "权重 配置 (JSON)",
    "Description": "描述",
    "Save suite": "保存 套件",
    "Benchmark registry": "基准 注册表",
    "Dataset cache": "数据集 缓存",
    "No source URL": "无 来源 URL",
    "Accept license": "接受 许可证",
    "Download and verify": "下载 和 验证",
    "Run preflight": "运行 预检",
    "Checking…": "正在检查…",
    "Preflight": "预检",
    "Evaluation runs": "评测 运行",
    "Inspect": "查看",
    "Run cap": "运行 上限",
    "Pause": "暂停",
    "Resume": "恢复",
    "Clone": "克隆",
    "Retry failed": "重试 失败",
    "Archive": "归档",
    "Task queue": "任务 队列",
    "Workers": "工作节点",
    "Worker": "工作节点",
    "Task": "任务",
    "Run": "运行",
    "Priority": "优先级",
    "Attempts": "尝试",
    "Created": "已创建",
    "Run A": "运行 一个",
    "Select completed run": "选择 已完成 运行",
    "Compare": "比较",
    "Report type": "报告 类型",
    "Prompt comparison": "提示词 比较",
    "Cost": "成本",
    "Related completed run": "相关 已完成 运行",
    "Select run": "选择 运行",
    "Generate PDF": "生成 PDF",
    "Generate JSON": "生成 JSON",
    "Create user": "创建 用户",
    "Email": "电子邮件",
    "Reviewer": "审查者",
    "User concurrency cap": "用户 并发 上限",
    "Action": "操作",
    "Database": "数据库",
    "Health": "健康",
    "Queue": "队列",
    "Disk": "磁盘",
    "Theme": "主题",
    "Workspace language": "工作区 语言",
    "Media preview": "媒体 预览",
    "Loading": "正在加载",
    "evidence…": "证据…",
    "Audio preview unavailable.": "音频 预览 不可用.",
    "Video preview unavailable.": "视频 预览 不可用.",
    "Download attached file": "下载 已附加 文件",
    "Sample evidence": "样本 证据",
    "Search samples": "搜索 样本",
    "All states": "全部 状态",
    "Succeeded": "成功",
    "Failed": "失败",
    "Pending": "待处理",
    "Running": "运行中",
    "Correctness": "正确性",
    "Correct": "正确",
    "Incorrect": "不正确",
    "Capability": "能力",
    "Modality": "模态",
    "Language": "语言",
    "Difficulty": "难度",
    "Error type": "错误 类型",
    "Any error": "任何 错误",
    "API error": "API 错误",
    "Parser error": "解析器 错误",
    "Judge": "裁判",
    "Disagreement": "分歧",
    "No disagreement": "无 分歧",
    "None": "无",
    "Load next 100 samples": "加载 下一步 100 样本",
    "Run executive summary": "运行 执行 摘要",
    "Completion": "完成情况",
    "Accuracy": "准确率",
    "Latency": "延迟",
    "Loading summary...": "正在加载 摘要...",
    "Durable run log": "持久 运行 日志",
    "Capability evidence": "能力 证据",
    "Score": "得分",
    "Samples": "样本",
    "Run signals": "运行 信号",
    "Loading next page…": "正在加载 下一步 页面…",
    "Reviewer ID": "审查者 ID",
    "Save review": "保存 审查",
    "Judge evidence": "裁判 证据",
    "Baseline run": "基线 运行",
    "No baseline": "无 基线",
    "Row": "行",
    "Column": "列",
    "Baseline / Δ": "基线 / Δ",
    "Errors": "错误",
    "Latency difference": "延迟 差异",
    "Cost difference": "成本 差异",
    "Output tokens": "输出 令牌",
    "Stored encrypted": "已存储 已加密",
    "Unlimited": "无限制",
    "production, vision": "生产, 视觉",
    "configured": "已配置",
    "cost not configured": "成本 未 已配置",
    "executed": "已执行",
    "paused": "已暂停",
    "resumed": "已恢复",
    "cancelled": "已取消",
    "single model": "单 模型",
    "multi model": "多 模型",
    "prompt comparison": "提示词 比较",
    "Run {{action}}.": "运行 {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} 下载 已暂停.",
  },
  "fr": {
    "Display name": "affichage nom",
    "Base URL": "base URL",
    "Model name": "modèle nom",
    "Protocol profile": "protocole profil",
    "API key": "API clé",
    "Custom headers (JSON)": "personnalisé en-têtes (JSON)",
    "Endpoint concurrency": "point de terminaison concurrence",
    "Shared API-key concurrency": "partagé clé API concurrence",
    "Requests / minute": "requêtes / minute",
    "Tokens / minute": "jetons / minute",
    "Requests / second": "requêtes / seconde",
    "Input tokens / minute": "entrée jetons / minute",
    "Output tokens / minute": "sortie jetons / minute",
    "Input / 1M tokens": "entrée / 1M jetons",
    "Output / 1M tokens": "sortie / 1M jetons",
    "Currency": "devise",
    "Tags (comma-separated)": "étiquettes (séparé par des virgules)",
    "Notes": "notes",
    "Saving...": "enregistrement...",
    "Save encrypted endpoint": "enregistrer chiffré point de terminaison",
    "Benchmark pack": "référentiel pack",
    "Built-in benchmark prompt": "intégré référentiel invite",
    "Run concurrency cap": "exécution concurrence plafond",
    "Models": "modèles",
    "Test connection": "tester connexion",
    "Probe capabilities": "sonder capacités",
    "Queue selected benchmark": "file sélectionné référentiel",
    "User: unknown": "utilisateur: inconnu",
    "User: supported": "utilisateur: pris en charge",
    "User: unsupported": "utilisateur: non pris en charge",
    "Benchmarks": "référentiels",
    "Benchmark": "référentiel",
    "Version": "version",
    "Source": "source",
    "Status": "statut",
    "Modalities": "modalités",
    "Operation": "opération",
    "Enable": "activer",
    "Disable": "désactiver",
    "Managed by pack": "géré par pack",
    "Queue on": "file sur",
    "Create prompt package": "créer invite package",
    "Name": "nom",
    "Prompt type": "invite type",
    "Official prompt": "officiel invite",
    "Platform default": "plateforme par défaut",
    "User custom": "utilisateur personnalisé",
    "Benchmark variant": "référentiel variante",
    "Language-specific": "spécifique à la langue",
    "System message": "système message",
    "User template": "utilisateur modèle",
    "Output format (JSON)": "sortie format (JSON)",
    "Response parser (JSON)": "réponse analyseur (JSON)",
    "Scoring rule (JSON)": "notation règle (JSON)",
    "Change log": "modifier journal",
    "Save versioned prompt": "enregistrer versionné invite",
    "Register dataset version": "enregistrer jeu de données version",
    "Dataset ID": "jeu de données ID",
    "Revision": "révision",
    "Source HTTPS URL": "source HTTPS URL",
    "Expected SHA-256 checksum": "attendu SHA-256 somme de contrôle",
    "Credential binding ID": "identifiant liaison ID",
    "License text": "licence texte",
    "Register dataset": "enregistrer jeu de données",
    "Preview": "aperçu",
    "Edit": "modifier",
    "Delete": "supprimer",
    "Cancel": "annuler",
    "Endpoint": "point de terminaison",
    "Select available endpoint": "sélectionner disponible point de terminaison",
    "Sample ID": "échantillon ID",
    "Prompt": "invite",
    "Expected text answer": "attendu texte réponse",
    "Uploaded media": "téléversé média",
    "Queue multimodal run": "file multimodal exécution",
    "Media asset upload": "média ressource téléverser",
    "Create evaluation suite": "créer évaluation suite",
    "Benchmarks (id@version)": "référentiels (ID@version)",
    "Prompt overrides (JSON)": "invite remplacements (JSON)",
    "Weight configuration (JSON)": "poids configuration (JSON)",
    "Description": "description",
    "Save suite": "enregistrer suite",
    "Benchmark registry": "référentiel registre",
    "Dataset cache": "jeu de données cache",
    "No source URL": "aucun source URL",
    "Accept license": "accepter licence",
    "Download and verify": "télécharger et vérifier",
    "Run preflight": "exécution pré-vérification",
    "Checking…": "vérification…",
    "Preflight": "pré-vérification",
    "Evaluation runs": "évaluation exécutions",
    "Inspect": "inspecter",
    "Run cap": "exécution plafond",
    "Pause": "mettre en pause",
    "Resume": "reprendre",
    "Clone": "cloner",
    "Retry failed": "réessayer échoué",
    "Archive": "archiver",
    "Task queue": "tâche file",
    "Workers": "agents",
    "Worker": "agent",
    "Task": "tâche",
    "Run": "exécution",
    "Priority": "priorité",
    "Attempts": "tentatives",
    "Created": "créé",
    "Run A": "exécution un",
    "Select completed run": "sélectionner terminé exécution",
    "Compare": "comparer",
    "Report type": "rapport type",
    "Prompt comparison": "invite comparaison",
    "Cost": "coût",
    "Related completed run": "associé terminé exécution",
    "Select run": "sélectionner exécution",
    "Generate PDF": "générer PDF",
    "Generate JSON": "générer JSON",
    "Create user": "créer utilisateur",
    "Email": "e-mail",
    "Reviewer": "évaluateur",
    "User concurrency cap": "utilisateur concurrence plafond",
    "Action": "action",
    "Database": "base de données",
    "Health": "santé",
    "Queue": "file",
    "Disk": "disque",
    "Theme": "thème",
    "Workspace language": "espace de travail langue",
    "Media preview": "média aperçu",
    "Loading": "chargement",
    "evidence…": "preuve…",
    "Audio preview unavailable.": "audio aperçu indisponible.",
    "Video preview unavailable.": "vidéo aperçu indisponible.",
    "Download attached file": "télécharger joint fichier",
    "Sample evidence": "échantillon preuve",
    "Search samples": "rechercher échantillons",
    "All states": "tous états",
    "Succeeded": "réussi",
    "Failed": "échoué",
    "Pending": "en attente",
    "Running": "en cours",
    "Correctness": "exactitude",
    "Correct": "correct",
    "Incorrect": "incorrect",
    "Capability": "capacité",
    "Modality": "modalité",
    "Language": "langue",
    "Difficulty": "difficulté",
    "Error type": "erreur type",
    "Any error": "tout erreur",
    "API error": "API erreur",
    "Parser error": "analyseur erreur",
    "Judge": "juge",
    "Disagreement": "désaccord",
    "No disagreement": "aucun désaccord",
    "None": "aucun",
    "Load next 100 samples": "charger suivant 100 échantillons",
    "Run executive summary": "exécution exécutif résumé",
    "Completion": "achèvement",
    "Accuracy": "précision",
    "Latency": "latence",
    "Loading summary...": "chargement résumé...",
    "Durable run log": "durable exécution journal",
    "Capability evidence": "capacité preuve",
    "Score": "score",
    "Samples": "échantillons",
    "Run signals": "exécution signaux",
    "Loading next page…": "chargement suivant page…",
    "Reviewer ID": "évaluateur ID",
    "Save review": "enregistrer révision",
    "Judge evidence": "juge preuve",
    "Baseline run": "référence exécution",
    "No baseline": "aucun référence",
    "Row": "ligne",
    "Column": "colonne",
    "Baseline / Δ": "référence / Δ",
    "Errors": "erreurs",
    "Latency difference": "latence différence",
    "Cost difference": "coût différence",
    "Output tokens": "sortie jetons",
    "Stored encrypted": "stocké chiffré",
    "Unlimited": "illimité",
    "production, vision": "production, vision",
    "configured": "configuré",
    "cost not configured": "coût non configuré",
    "executed": "exécutée",
    "paused": "mise en pause",
    "resumed": "reprise",
    "cancelled": "annulée",
    "single model": "unique modèle",
    "multi model": "multi modèle",
    "prompt comparison": "invite comparaison",
    "Run {{action}}.": "exécution {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} télécharger mise en pause.",
  },
  "de": {
    "Display name": "Anzeige Name",
    "Base URL": "Basis URL",
    "Model name": "Modell Name",
    "Protocol profile": "Protokoll Profil",
    "API key": "API Schlüssel",
    "Custom headers (JSON)": "benutzerdefiniert Header (JSON)",
    "Endpoint concurrency": "Endpunkt Parallelität",
    "Shared API-key concurrency": "geteilt API-Schlüssel Parallelität",
    "Requests / minute": "Anfragen / Minute",
    "Tokens / minute": "Token / Minute",
    "Requests / second": "Anfragen / Sekunde",
    "Input tokens / minute": "Eingabe Token / Minute",
    "Output tokens / minute": "Ausgabe Token / Minute",
    "Input / 1M tokens": "Eingabe / 1M Token",
    "Output / 1M tokens": "Ausgabe / 1M Token",
    "Currency": "Währung",
    "Tags (comma-separated)": "Tags (kommagetrennt)",
    "Notes": "Notizen",
    "Saving...": "speichert...",
    "Save encrypted endpoint": "speichern verschlüsselt Endpunkt",
    "Benchmark pack": "Benchmark Paket",
    "Built-in benchmark prompt": "integriert Benchmark Prompt",
    "Run concurrency cap": "Ausführung Parallelität Obergrenze",
    "Models": "Modelle",
    "Test connection": "testen Verbindung",
    "Probe capabilities": "prüfen Fähigkeiten",
    "Queue selected benchmark": "Warteschlange ausgewählt Benchmark",
    "User: unknown": "Benutzer: unbekannt",
    "User: supported": "Benutzer: unterstützt",
    "User: unsupported": "Benutzer: nicht unterstützt",
    "Benchmarks": "Benchmarks",
    "Benchmark": "Benchmark",
    "Version": "Version",
    "Source": "Quelle",
    "Status": "Status",
    "Modalities": "Modalitäten",
    "Operation": "Vorgang",
    "Enable": "aktivieren",
    "Disable": "deaktivieren",
    "Managed by pack": "verwaltet von Paket",
    "Queue on": "Warteschlange auf",
    "Create prompt package": "erstellen Prompt Paket",
    "Name": "Name",
    "Prompt type": "Prompt Typ",
    "Official prompt": "offiziell Prompt",
    "Platform default": "Plattform Standard",
    "User custom": "Benutzer benutzerdefiniert",
    "Benchmark variant": "Benchmark Variante",
    "Language-specific": "sprachspezifisch",
    "System message": "System Nachricht",
    "User template": "Benutzer Vorlage",
    "Output format (JSON)": "Ausgabe Format (JSON)",
    "Response parser (JSON)": "Antwort Parser (JSON)",
    "Scoring rule (JSON)": "Bewertung Regel (JSON)",
    "Change log": "ändern Protokoll",
    "Save versioned prompt": "speichern versioniert Prompt",
    "Register dataset version": "registrieren Datensatz Version",
    "Dataset ID": "Datensatz ID",
    "Revision": "Revision",
    "Source HTTPS URL": "Quelle HTTPS URL",
    "Expected SHA-256 checksum": "erwartet SHA-256 Prüfsumme",
    "Credential binding ID": "Anmeldeinformation Bindung ID",
    "License text": "Lizenz Text",
    "Register dataset": "registrieren Datensatz",
    "Preview": "Vorschau",
    "Edit": "bearbeiten",
    "Delete": "löschen",
    "Cancel": "abbrechen",
    "Endpoint": "Endpunkt",
    "Select available endpoint": "auswählen verfügbar Endpunkt",
    "Sample ID": "Stichprobe ID",
    "Prompt": "Prompt",
    "Expected text answer": "erwartet Text Antwort",
    "Uploaded media": "hochgeladen Medien",
    "Queue multimodal run": "Warteschlange multimodal Ausführung",
    "Media asset upload": "Medien Asset hochladen",
    "Create evaluation suite": "erstellen Bewertung Suite",
    "Benchmarks (id@version)": "Benchmarks (ID@Version)",
    "Prompt overrides (JSON)": "Prompt Überschreibungen (JSON)",
    "Weight configuration (JSON)": "Gewichtung Konfiguration (JSON)",
    "Description": "Beschreibung",
    "Save suite": "speichern Suite",
    "Benchmark registry": "Benchmark Registrierung",
    "Dataset cache": "Datensatz Cache",
    "No source URL": "keine Quelle URL",
    "Accept license": "akzeptieren Lizenz",
    "Download and verify": "herunterladen und prüfen",
    "Run preflight": "Ausführung Vorprüfung",
    "Checking…": "Prüfung…",
    "Preflight": "Vorprüfung",
    "Evaluation runs": "Bewertung Ausführungen",
    "Inspect": "prüfen",
    "Run cap": "Ausführung Obergrenze",
    "Pause": "pausieren",
    "Resume": "fortsetzen",
    "Clone": "klonen",
    "Retry failed": "wiederholen fehlgeschlagen",
    "Archive": "archivieren",
    "Task queue": "Aufgabe Warteschlange",
    "Workers": "Worker",
    "Worker": "Worker",
    "Task": "Aufgabe",
    "Run": "Ausführung",
    "Priority": "Priorität",
    "Attempts": "Versuche",
    "Created": "erstellt",
    "Run A": "Ausführung ein",
    "Select completed run": "auswählen abgeschlossen Ausführung",
    "Compare": "vergleichen",
    "Report type": "Bericht Typ",
    "Prompt comparison": "Prompt Vergleich",
    "Cost": "Kosten",
    "Related completed run": "zugehörig abgeschlossen Ausführung",
    "Select run": "auswählen Ausführung",
    "Generate PDF": "generieren PDF",
    "Generate JSON": "generieren JSON",
    "Create user": "erstellen Benutzer",
    "Email": "E-Mail",
    "Reviewer": "Prüfer",
    "User concurrency cap": "Benutzer Parallelität Obergrenze",
    "Action": "Aktion",
    "Database": "Datenbank",
    "Health": "Zustand",
    "Queue": "Warteschlange",
    "Disk": "Datenträger",
    "Theme": "Design",
    "Workspace language": "Arbeitsbereich Sprache",
    "Media preview": "Medien Vorschau",
    "Loading": "wird geladen",
    "evidence…": "Nachweis…",
    "Audio preview unavailable.": "Audio Vorschau nicht verfügbar.",
    "Video preview unavailable.": "Video Vorschau nicht verfügbar.",
    "Download attached file": "herunterladen angehängt Datei",
    "Sample evidence": "Stichprobe Nachweis",
    "Search samples": "suchen Stichproben",
    "All states": "alle Zustände",
    "Succeeded": "erfolgreich",
    "Failed": "fehlgeschlagen",
    "Pending": "ausstehend",
    "Running": "laufend",
    "Correctness": "Korrektheit",
    "Correct": "richtig",
    "Incorrect": "falsch",
    "Capability": "Fähigkeit",
    "Modality": "Modalität",
    "Language": "Sprache",
    "Difficulty": "Schwierigkeit",
    "Error type": "Fehler Typ",
    "Any error": "beliebig Fehler",
    "API error": "API Fehler",
    "Parser error": "Parser Fehler",
    "Judge": "Bewertung",
    "Disagreement": "Uneinigkeit",
    "No disagreement": "keine Uneinigkeit",
    "None": "keine",
    "Load next 100 samples": "laden nächste 100 Stichproben",
    "Run executive summary": "Ausführung Management Zusammenfassung",
    "Completion": "Abschluss",
    "Accuracy": "Genauigkeit",
    "Latency": "Latenz",
    "Loading summary...": "wird geladen Zusammenfassung...",
    "Durable run log": "beständig Ausführung Protokoll",
    "Capability evidence": "Fähigkeit Nachweis",
    "Score": "Punktzahl",
    "Samples": "Stichproben",
    "Run signals": "Ausführung Signale",
    "Loading next page…": "wird geladen nächste Seite…",
    "Reviewer ID": "Prüfer ID",
    "Save review": "speichern Überprüfung",
    "Judge evidence": "Bewertung Nachweis",
    "Baseline run": "Basislinie Ausführung",
    "No baseline": "keine Basislinie",
    "Row": "Zeile",
    "Column": "Spalte",
    "Baseline / Δ": "Basislinie / Δ",
    "Errors": "Fehler",
    "Latency difference": "Latenz Differenz",
    "Cost difference": "Kosten Differenz",
    "Output tokens": "Ausgabe Token",
    "Stored encrypted": "gespeichert verschlüsselt",
    "Unlimited": "unbegrenzt",
    "production, vision": "Produktion, Vision",
    "configured": "konfiguriert",
    "cost not configured": "Kosten nicht konfiguriert",
    "executed": "ausgeführt",
    "paused": "pausiert",
    "resumed": "fortgesetzt",
    "cancelled": "abgebrochen",
    "single model": "einzel Modell",
    "multi model": "mehrere Modell",
    "prompt comparison": "Prompt Vergleich",
    "Run {{action}}.": "Ausführung {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} herunterladen pausiert.",
  },
  "ru": {
    "Display name": "отображение имя",
    "Base URL": "база URL",
    "Model name": "модель имя",
    "Protocol profile": "протокол профиль",
    "API key": "API ключ",
    "Custom headers (JSON)": "пользовательский заголовки (JSON)",
    "Endpoint concurrency": "конечная точка параллелизм",
    "Shared API-key concurrency": "общий ключ API параллелизм",
    "Requests / minute": "запросы / минута",
    "Tokens / minute": "токены / минута",
    "Requests / second": "запросы / секунда",
    "Input tokens / minute": "ввод токены / минута",
    "Output tokens / minute": "вывод токены / минута",
    "Input / 1M tokens": "ввод / 1млн токены",
    "Output / 1M tokens": "вывод / 1млн токены",
    "Currency": "валюта",
    "Tags (comma-separated)": "теги (разделённый запятыми)",
    "Notes": "примечания",
    "Saving...": "сохранение...",
    "Save encrypted endpoint": "сохранить зашифрованный конечная точка",
    "Benchmark pack": "бенчмарк пакет",
    "Built-in benchmark prompt": "встроенный бенчмарк запрос",
    "Run concurrency cap": "запуск параллелизм лимит",
    "Models": "модели",
    "Test connection": "тест подключение",
    "Probe capabilities": "зондировать возможности",
    "Queue selected benchmark": "очередь выбранный бенчмарк",
    "User: unknown": "пользователь: неизвестный",
    "User: supported": "пользователь: поддерживается",
    "User: unsupported": "пользователь: не поддерживается",
    "Benchmarks": "бенчмарки",
    "Benchmark": "бенчмарк",
    "Version": "версия",
    "Source": "источник",
    "Status": "статус",
    "Modalities": "модальности",
    "Operation": "операция",
    "Enable": "включить",
    "Disable": "отключить",
    "Managed by pack": "управляемый по пакет",
    "Queue on": "очередь на",
    "Create prompt package": "создать запрос пакет",
    "Name": "имя",
    "Prompt type": "запрос тип",
    "Official prompt": "официальный запрос",
    "Platform default": "платформа по умолчанию",
    "User custom": "пользователь пользовательский",
    "Benchmark variant": "бенчмарк вариант",
    "Language-specific": "языковой",
    "System message": "система сообщение",
    "User template": "пользователь шаблон",
    "Output format (JSON)": "вывод формат (JSON)",
    "Response parser (JSON)": "ответ парсер (JSON)",
    "Scoring rule (JSON)": "оценивание правило (JSON)",
    "Change log": "изменить журнал",
    "Save versioned prompt": "сохранить версионированный запрос",
    "Register dataset version": "зарегистрировать набор данных версия",
    "Dataset ID": "набор данных ID",
    "Revision": "редакция",
    "Source HTTPS URL": "источник HTTPS URL",
    "Expected SHA-256 checksum": "ожидаемый SHA-256 контрольная сумма",
    "Credential binding ID": "учётные данные привязка ID",
    "License text": "лицензия текст",
    "Register dataset": "зарегистрировать набор данных",
    "Preview": "предпросмотр",
    "Edit": "изменить",
    "Delete": "удалить",
    "Cancel": "отменить",
    "Endpoint": "конечная точка",
    "Select available endpoint": "выбрать доступный конечная точка",
    "Sample ID": "образец ID",
    "Prompt": "запрос",
    "Expected text answer": "ожидаемый текст ответ",
    "Uploaded media": "загружен медиа",
    "Queue multimodal run": "очередь мультимодальный запуск",
    "Media asset upload": "медиа ресурс загрузить",
    "Create evaluation suite": "создать оценка набор",
    "Benchmarks (id@version)": "бенчмарки (ID@версия)",
    "Prompt overrides (JSON)": "запрос переопределения (JSON)",
    "Weight configuration (JSON)": "вес конфигурация (JSON)",
    "Description": "описание",
    "Save suite": "сохранить набор",
    "Benchmark registry": "бенчмарк реестр",
    "Dataset cache": "набор данных кэш",
    "No source URL": "нет источник URL",
    "Accept license": "принять лицензия",
    "Download and verify": "скачать и проверить",
    "Run preflight": "запуск предпроверка",
    "Checking…": "проверка…",
    "Preflight": "предпроверка",
    "Evaluation runs": "оценка запуски",
    "Inspect": "проверить",
    "Run cap": "запуск лимит",
    "Pause": "приостановить",
    "Resume": "возобновить",
    "Clone": "клонировать",
    "Retry failed": "повторить сбой",
    "Archive": "архивировать",
    "Task queue": "задача очередь",
    "Workers": "воркеры",
    "Worker": "воркер",
    "Task": "задача",
    "Run": "запуск",
    "Priority": "приоритет",
    "Attempts": "попытки",
    "Created": "создан",
    "Run A": "запуск один",
    "Select completed run": "выбрать завершено запуск",
    "Compare": "сравнить",
    "Report type": "отчёт тип",
    "Prompt comparison": "запрос сравнение",
    "Cost": "стоимость",
    "Related completed run": "связанный завершено запуск",
    "Select run": "выбрать запуск",
    "Generate PDF": "создать PDF",
    "Generate JSON": "создать JSON",
    "Create user": "создать пользователь",
    "Email": "электронная почта",
    "Reviewer": "рецензент",
    "User concurrency cap": "пользователь параллелизм лимит",
    "Action": "действие",
    "Database": "база данных",
    "Health": "состояние",
    "Queue": "очередь",
    "Disk": "диск",
    "Theme": "тема",
    "Workspace language": "рабочее пространство язык",
    "Media preview": "медиа предпросмотр",
    "Loading": "загрузка",
    "evidence…": "доказательство…",
    "Audio preview unavailable.": "аудио предпросмотр недоступно.",
    "Video preview unavailable.": "видео предпросмотр недоступно.",
    "Download attached file": "скачать прикреплён файл",
    "Sample evidence": "образец доказательство",
    "Search samples": "поиск образцы",
    "All states": "все состояния",
    "Succeeded": "успешно",
    "Failed": "сбой",
    "Pending": "ожидающий",
    "Running": "выполняется",
    "Correctness": "правильность",
    "Correct": "верный",
    "Incorrect": "неверный",
    "Capability": "возможность",
    "Modality": "модальность",
    "Language": "язык",
    "Difficulty": "сложность",
    "Error type": "ошибка тип",
    "Any error": "любой ошибка",
    "API error": "API ошибка",
    "Parser error": "парсер ошибка",
    "Judge": "судья",
    "Disagreement": "разногласие",
    "No disagreement": "нет разногласие",
    "None": "нет",
    "Load next 100 samples": "загрузить следующий 100 образцы",
    "Run executive summary": "запуск исполнительный сводка",
    "Completion": "завершение",
    "Accuracy": "точность",
    "Latency": "задержка",
    "Loading summary...": "загрузка сводка...",
    "Durable run log": "долговечный запуск журнал",
    "Capability evidence": "возможность доказательство",
    "Score": "оценка",
    "Samples": "образцы",
    "Run signals": "запуск сигналы",
    "Loading next page…": "загрузка следующий страница…",
    "Reviewer ID": "рецензент ID",
    "Save review": "сохранить проверка",
    "Judge evidence": "судья доказательство",
    "Baseline run": "базовый запуск",
    "No baseline": "нет базовый",
    "Row": "строка",
    "Column": "столбец",
    "Baseline / Δ": "базовый / Δ",
    "Errors": "ошибки",
    "Latency difference": "задержка разница",
    "Cost difference": "стоимость разница",
    "Output tokens": "вывод токены",
    "Stored encrypted": "сохранён зашифрованный",
    "Unlimited": "без ограничений",
    "production, vision": "производство, зрение",
    "configured": "настроен",
    "cost not configured": "стоимость не настроен",
    "executed": "выполнен",
    "paused": "приостановлен",
    "resumed": "возобновлён",
    "cancelled": "отменён",
    "single model": "одна модель",
    "multi model": "несколько модель",
    "prompt comparison": "запрос сравнение",
    "Run {{action}}.": "запуск {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} скачать приостановлен.",
  },
  "ja": {
    "Display name": "表示 名前",
    "Base URL": "ベース URL",
    "Model name": "モデル 名前",
    "Protocol profile": "プロトコル プロファイル",
    "API key": "API キー",
    "Custom headers (JSON)": "カスタム ヘッダー (JSON)",
    "Endpoint concurrency": "エンドポイント 同時実行",
    "Shared API-key concurrency": "共有 API キー 同時実行",
    "Requests / minute": "リクエスト / 分",
    "Tokens / minute": "トークン / 分",
    "Requests / second": "リクエスト / 秒",
    "Input tokens / minute": "入力 トークン / 分",
    "Output tokens / minute": "出力 トークン / 分",
    "Input / 1M tokens": "入力 / 1M トークン",
    "Output / 1M tokens": "出力 / 1M トークン",
    "Currency": "通貨",
    "Tags (comma-separated)": "タグ (カンマ区切り)",
    "Notes": "メモ",
    "Saving...": "保存中...",
    "Save encrypted endpoint": "保存 暗号化済み エンドポイント",
    "Benchmark pack": "ベンチマーク パック",
    "Built-in benchmark prompt": "組み込み ベンチマーク プロンプト",
    "Run concurrency cap": "実行 同時実行 上限",
    "Models": "モデル",
    "Test connection": "テスト 接続",
    "Probe capabilities": "検出 機能",
    "Queue selected benchmark": "キュー 選択済み ベンチマーク",
    "User: unknown": "ユーザー: 不明",
    "User: supported": "ユーザー: 対応",
    "User: unsupported": "ユーザー: 未対応",
    "Benchmarks": "ベンチマーク",
    "Benchmark": "ベンチマーク",
    "Version": "バージョン",
    "Source": "ソース",
    "Status": "状態",
    "Modalities": "モダリティ",
    "Operation": "操作",
    "Enable": "有効化",
    "Disable": "無効化",
    "Managed by pack": "管理済み により パック",
    "Queue on": "キュー で",
    "Create prompt package": "作成 プロンプト パッケージ",
    "Name": "名前",
    "Prompt type": "プロンプト 種類",
    "Official prompt": "公式 プロンプト",
    "Platform default": "プラットフォーム 既定",
    "User custom": "ユーザー カスタム",
    "Benchmark variant": "ベンチマーク バリアント",
    "Language-specific": "言語固有",
    "System message": "システム メッセージ",
    "User template": "ユーザー テンプレート",
    "Output format (JSON)": "出力 形式 (JSON)",
    "Response parser (JSON)": "応答 パーサー (JSON)",
    "Scoring rule (JSON)": "採点 ルール (JSON)",
    "Change log": "変更 ログ",
    "Save versioned prompt": "保存 バージョン管理済み プロンプト",
    "Register dataset version": "登録 データセット バージョン",
    "Dataset ID": "データセット ID",
    "Revision": "改訂",
    "Source HTTPS URL": "ソース HTTPS URL",
    "Expected SHA-256 checksum": "期待 SHA-256 チェックサム",
    "Credential binding ID": "資格情報 バインド ID",
    "License text": "ライセンス テキスト",
    "Register dataset": "登録 データセット",
    "Preview": "プレビュー",
    "Edit": "編集",
    "Delete": "削除",
    "Cancel": "キャンセル",
    "Endpoint": "エンドポイント",
    "Select available endpoint": "選択 利用可能 エンドポイント",
    "Sample ID": "サンプル ID",
    "Prompt": "プロンプト",
    "Expected text answer": "期待 テキスト 回答",
    "Uploaded media": "アップロード済み メディア",
    "Queue multimodal run": "キュー マルチモーダル 実行",
    "Media asset upload": "メディア アセット アップロード",
    "Create evaluation suite": "作成 評価 スイート",
    "Benchmarks (id@version)": "ベンチマーク (ID@バージョン)",
    "Prompt overrides (JSON)": "プロンプト 上書き (JSON)",
    "Weight configuration (JSON)": "重み 設定 (JSON)",
    "Description": "説明",
    "Save suite": "保存 スイート",
    "Benchmark registry": "ベンチマーク レジストリ",
    "Dataset cache": "データセット キャッシュ",
    "No source URL": "なし ソース URL",
    "Accept license": "承諾 ライセンス",
    "Download and verify": "ダウンロード と 確認",
    "Run preflight": "実行 事前確認",
    "Checking…": "確認中…",
    "Preflight": "事前確認",
    "Evaluation runs": "評価 実行",
    "Inspect": "確認",
    "Run cap": "実行 上限",
    "Pause": "一時停止",
    "Resume": "再開",
    "Clone": "複製",
    "Retry failed": "再試行 失敗",
    "Archive": "アーカイブ",
    "Task queue": "タスク キュー",
    "Workers": "ワーカー",
    "Worker": "ワーカー",
    "Task": "タスク",
    "Run": "実行",
    "Priority": "優先度",
    "Attempts": "試行",
    "Created": "作成済み",
    "Run A": "実行 1つの",
    "Select completed run": "選択 完了 実行",
    "Compare": "比較",
    "Report type": "レポート 種類",
    "Prompt comparison": "プロンプト 比較",
    "Cost": "コスト",
    "Related completed run": "関連 完了 実行",
    "Select run": "選択 実行",
    "Generate PDF": "生成 PDF",
    "Generate JSON": "生成 JSON",
    "Create user": "作成 ユーザー",
    "Email": "メール",
    "Reviewer": "レビュアー",
    "User concurrency cap": "ユーザー 同時実行 上限",
    "Action": "操作",
    "Database": "データベース",
    "Health": "正常性",
    "Queue": "キュー",
    "Disk": "ディスク",
    "Theme": "テーマ",
    "Workspace language": "ワークスペース 言語",
    "Media preview": "メディア プレビュー",
    "Loading": "読み込み中",
    "evidence…": "証拠…",
    "Audio preview unavailable.": "音声 プレビュー 利用不可.",
    "Video preview unavailable.": "動画 プレビュー 利用不可.",
    "Download attached file": "ダウンロード 添付済み ファイル",
    "Sample evidence": "サンプル 証拠",
    "Search samples": "検索 サンプル",
    "All states": "すべて 状態",
    "Succeeded": "成功",
    "Failed": "失敗",
    "Pending": "保留中",
    "Running": "実行中",
    "Correctness": "正確性",
    "Correct": "正解",
    "Incorrect": "不正解",
    "Capability": "機能",
    "Modality": "モダリティ",
    "Language": "言語",
    "Difficulty": "難易度",
    "Error type": "エラー 種類",
    "Any error": "任意 エラー",
    "API error": "API エラー",
    "Parser error": "パーサー エラー",
    "Judge": "判定",
    "Disagreement": "不一致",
    "No disagreement": "なし 不一致",
    "None": "なし",
    "Load next 100 samples": "読み込む 次 100 サンプル",
    "Run executive summary": "実行 エグゼクティブ 概要",
    "Completion": "完了",
    "Accuracy": "精度",
    "Latency": "レイテンシ",
    "Loading summary...": "読み込み中 概要...",
    "Durable run log": "永続 実行 ログ",
    "Capability evidence": "機能 証拠",
    "Score": "スコア",
    "Samples": "サンプル",
    "Run signals": "実行 シグナル",
    "Loading next page…": "読み込み中 次 ページ…",
    "Reviewer ID": "レビュアー ID",
    "Save review": "保存 レビュー",
    "Judge evidence": "判定 証拠",
    "Baseline run": "ベースライン 実行",
    "No baseline": "なし ベースライン",
    "Row": "行",
    "Column": "列",
    "Baseline / Δ": "ベースライン / Δ",
    "Errors": "エラー",
    "Latency difference": "レイテンシ 差分",
    "Cost difference": "コスト 差分",
    "Output tokens": "出力 トークン",
    "Stored encrypted": "保存済み 暗号化済み",
    "Unlimited": "無制限",
    "production, vision": "本番, ビジョン",
    "configured": "設定済み",
    "cost not configured": "コスト ない 設定済み",
    "executed": "実行済み",
    "paused": "一時停止済み",
    "resumed": "再開済み",
    "cancelled": "キャンセル済み",
    "single model": "単一 モデル",
    "multi model": "複数 モデル",
    "prompt comparison": "プロンプト 比較",
    "Run {{action}}.": "実行 {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} ダウンロード 一時停止済み.",
  },
  "ko": {
    "Display name": "표시 이름",
    "Base URL": "기본 URL",
    "Model name": "모델 이름",
    "Protocol profile": "프로토콜 프로필",
    "API key": "API 키",
    "Custom headers (JSON)": "사용자 지정 헤더 (JSON)",
    "Endpoint concurrency": "엔드포인트 동시 실행",
    "Shared API-key concurrency": "공유 API 키 동시 실행",
    "Requests / minute": "요청 / 분",
    "Tokens / minute": "토큰 / 분",
    "Requests / second": "요청 / 초",
    "Input tokens / minute": "입력 토큰 / 분",
    "Output tokens / minute": "출력 토큰 / 분",
    "Input / 1M tokens": "입력 / 1M 토큰",
    "Output / 1M tokens": "출력 / 1M 토큰",
    "Currency": "통화",
    "Tags (comma-separated)": "태그 (쉼표로 구분)",
    "Notes": "메모",
    "Saving...": "저장 중...",
    "Save encrypted endpoint": "저장 암호화됨 엔드포인트",
    "Benchmark pack": "벤치마크 팩",
    "Built-in benchmark prompt": "내장 벤치마크 프롬프트",
    "Run concurrency cap": "실행 동시 실행 한도",
    "Models": "모델",
    "Test connection": "테스트 연결",
    "Probe capabilities": "탐색 기능",
    "Queue selected benchmark": "대기열 선택됨 벤치마크",
    "User: unknown": "사용자: 알 수 없음",
    "User: supported": "사용자: 지원됨",
    "User: unsupported": "사용자: 지원되지 않음",
    "Benchmarks": "벤치마크",
    "Benchmark": "벤치마크",
    "Version": "버전",
    "Source": "소스",
    "Status": "상태",
    "Modalities": "모달리티",
    "Operation": "작업",
    "Enable": "활성화",
    "Disable": "비활성화",
    "Managed by pack": "관리됨 으로 팩",
    "Queue on": "대기열 에서",
    "Create prompt package": "생성 프롬프트 패키지",
    "Name": "이름",
    "Prompt type": "프롬프트 유형",
    "Official prompt": "공식 프롬프트",
    "Platform default": "플랫폼 기본",
    "User custom": "사용자 사용자 지정",
    "Benchmark variant": "벤치마크 변형",
    "Language-specific": "언어별",
    "System message": "시스템 메시지",
    "User template": "사용자 템플릿",
    "Output format (JSON)": "출력 형식 (JSON)",
    "Response parser (JSON)": "응답 파서 (JSON)",
    "Scoring rule (JSON)": "채점 규칙 (JSON)",
    "Change log": "변경 로그",
    "Save versioned prompt": "저장 버전 관리됨 프롬프트",
    "Register dataset version": "등록 데이터 세트 버전",
    "Dataset ID": "데이터 세트 ID",
    "Revision": "개정",
    "Source HTTPS URL": "소스 HTTPS URL",
    "Expected SHA-256 checksum": "예상 SHA-256 체크섬",
    "Credential binding ID": "자격 증명 바인딩 ID",
    "License text": "라이선스 텍스트",
    "Register dataset": "등록 데이터 세트",
    "Preview": "미리보기",
    "Edit": "편집",
    "Delete": "삭제",
    "Cancel": "취소",
    "Endpoint": "엔드포인트",
    "Select available endpoint": "선택 사용 가능 엔드포인트",
    "Sample ID": "샘플 ID",
    "Prompt": "프롬프트",
    "Expected text answer": "예상 텍스트 답변",
    "Uploaded media": "업로드됨 미디어",
    "Queue multimodal run": "대기열 멀티모달 실행",
    "Media asset upload": "미디어 자산 업로드",
    "Create evaluation suite": "생성 평가 스위트",
    "Benchmarks (id@version)": "벤치마크 (ID@버전)",
    "Prompt overrides (JSON)": "프롬프트 재정의 (JSON)",
    "Weight configuration (JSON)": "가중치 구성 (JSON)",
    "Description": "설명",
    "Save suite": "저장 스위트",
    "Benchmark registry": "벤치마크 레지스트리",
    "Dataset cache": "데이터 세트 캐시",
    "No source URL": "없음 소스 URL",
    "Accept license": "수락 라이선스",
    "Download and verify": "다운로드 및 검증",
    "Run preflight": "실행 사전 점검",
    "Checking…": "확인 중…",
    "Preflight": "사전 점검",
    "Evaluation runs": "평가 실행",
    "Inspect": "검사",
    "Run cap": "실행 한도",
    "Pause": "일시 중지",
    "Resume": "재개",
    "Clone": "복제",
    "Retry failed": "재시도 실패",
    "Archive": "보관",
    "Task queue": "작업 대기열",
    "Workers": "워커",
    "Worker": "워커",
    "Task": "작업",
    "Run": "실행",
    "Priority": "우선순위",
    "Attempts": "시도",
    "Created": "생성됨",
    "Run A": "실행 하나의",
    "Select completed run": "선택 완료됨 실행",
    "Compare": "비교",
    "Report type": "보고서 유형",
    "Prompt comparison": "프롬프트 비교",
    "Cost": "비용",
    "Related completed run": "관련 완료됨 실행",
    "Select run": "선택 실행",
    "Generate PDF": "생성 PDF",
    "Generate JSON": "생성 JSON",
    "Create user": "생성 사용자",
    "Email": "이메일",
    "Reviewer": "검토자",
    "User concurrency cap": "사용자 동시 실행 한도",
    "Action": "작업",
    "Database": "데이터베이스",
    "Health": "상태",
    "Queue": "대기열",
    "Disk": "디스크",
    "Theme": "테마",
    "Workspace language": "작업 공간 언어",
    "Media preview": "미디어 미리보기",
    "Loading": "불러오는 중",
    "evidence…": "증거…",
    "Audio preview unavailable.": "오디오 미리보기 사용 불가.",
    "Video preview unavailable.": "비디오 미리보기 사용 불가.",
    "Download attached file": "다운로드 첨부됨 파일",
    "Sample evidence": "샘플 증거",
    "Search samples": "검색 샘플",
    "All states": "전체 상태",
    "Succeeded": "성공",
    "Failed": "실패",
    "Pending": "보류",
    "Running": "실행 중",
    "Correctness": "정확성",
    "Correct": "정답",
    "Incorrect": "오답",
    "Capability": "기능",
    "Modality": "모달리티",
    "Language": "언어",
    "Difficulty": "난이도",
    "Error type": "오류 유형",
    "Any error": "모든 오류",
    "API error": "API 오류",
    "Parser error": "파서 오류",
    "Judge": "심사",
    "Disagreement": "불일치",
    "No disagreement": "없음 불일치",
    "None": "없음",
    "Load next 100 samples": "불러오기 다음 100 샘플",
    "Run executive summary": "실행 요약 요약",
    "Completion": "완료",
    "Accuracy": "정확도",
    "Latency": "지연 시간",
    "Loading summary...": "불러오는 중 요약...",
    "Durable run log": "지속 실행 로그",
    "Capability evidence": "기능 증거",
    "Score": "점수",
    "Samples": "샘플",
    "Run signals": "실행 신호",
    "Loading next page…": "불러오는 중 다음 페이지…",
    "Reviewer ID": "검토자 ID",
    "Save review": "저장 검토",
    "Judge evidence": "심사 증거",
    "Baseline run": "기준선 실행",
    "No baseline": "없음 기준선",
    "Row": "행",
    "Column": "열",
    "Baseline / Δ": "기준선 / Δ",
    "Errors": "오류",
    "Latency difference": "지연 시간 차이",
    "Cost difference": "비용 차이",
    "Output tokens": "출력 토큰",
    "Stored encrypted": "저장됨 암호화됨",
    "Unlimited": "무제한",
    "production, vision": "프로덕션, 비전",
    "configured": "구성됨",
    "cost not configured": "비용 아님 구성됨",
    "executed": "실행됨",
    "paused": "일시 중지됨",
    "resumed": "재개됨",
    "cancelled": "취소됨",
    "single model": "단일 모델",
    "multi model": "다중 모델",
    "prompt comparison": "프롬프트 비교",
    "Run {{action}}.": "실행 {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} 다운로드 일시 중지됨.",
  },
  "ms": {
    "Display name": "paparan nama",
    "Base URL": "asas URL",
    "Model name": "model nama",
    "Protocol profile": "protokol profil",
    "API key": "API kunci",
    "Custom headers (JSON)": "tersuai pengepala (JSON)",
    "Endpoint concurrency": "titik akhir serentak",
    "Shared API-key concurrency": "dikongsi kunci API serentak",
    "Requests / minute": "permintaan / minit",
    "Tokens / minute": "token / minit",
    "Requests / second": "permintaan / saat",
    "Input tokens / minute": "input token / minit",
    "Output tokens / minute": "output token / minit",
    "Input / 1M tokens": "input / 1J token",
    "Output / 1M tokens": "output / 1J token",
    "Currency": "mata wang",
    "Tags (comma-separated)": "tag (dipisahkan koma)",
    "Notes": "nota",
    "Saving...": "menyimpan...",
    "Save encrypted endpoint": "simpan disulitkan titik akhir",
    "Benchmark pack": "penanda aras pek",
    "Built-in benchmark prompt": "terbina dalam penanda aras gesaan",
    "Run concurrency cap": "larian serentak had",
    "Models": "model",
    "Test connection": "uji sambungan",
    "Probe capabilities": "siasat keupayaan",
    "Queue selected benchmark": "baris dipilih penanda aras",
    "User: unknown": "pengguna: tidak diketahui",
    "User: supported": "pengguna: disokong",
    "User: unsupported": "pengguna: tidak disokong",
    "Benchmarks": "penanda aras",
    "Benchmark": "penanda aras",
    "Version": "versi",
    "Source": "sumber",
    "Status": "status",
    "Modalities": "modaliti",
    "Operation": "operasi",
    "Enable": "dayakan",
    "Disable": "nyahdayakan",
    "Managed by pack": "diuruskan oleh pek",
    "Queue on": "baris pada",
    "Create prompt package": "cipta gesaan pakej",
    "Name": "nama",
    "Prompt type": "gesaan jenis",
    "Official prompt": "rasmi gesaan",
    "Platform default": "platform lalai",
    "User custom": "pengguna tersuai",
    "Benchmark variant": "penanda aras varian",
    "Language-specific": "khusus bahasa",
    "System message": "sistem mesej",
    "User template": "pengguna templat",
    "Output format (JSON)": "output format (JSON)",
    "Response parser (JSON)": "respons penghurai (JSON)",
    "Scoring rule (JSON)": "pemarkahan peraturan (JSON)",
    "Change log": "ubah log",
    "Save versioned prompt": "simpan berversi gesaan",
    "Register dataset version": "daftar set data versi",
    "Dataset ID": "set data ID",
    "Revision": "semakan",
    "Source HTTPS URL": "sumber HTTPS URL",
    "Expected SHA-256 checksum": "dijangka SHA-256 jumlah semak",
    "Credential binding ID": "kelayakan pengikatan ID",
    "License text": "lesen teks",
    "Register dataset": "daftar set data",
    "Preview": "pratonton",
    "Edit": "sunting",
    "Delete": "padam",
    "Cancel": "batal",
    "Endpoint": "titik akhir",
    "Select available endpoint": "pilih tersedia titik akhir",
    "Sample ID": "sampel ID",
    "Prompt": "gesaan",
    "Expected text answer": "dijangka teks jawapan",
    "Uploaded media": "dimuat naik media",
    "Queue multimodal run": "baris multimodal larian",
    "Media asset upload": "media aset muat naik",
    "Create evaluation suite": "cipta penilaian set",
    "Benchmarks (id@version)": "penanda aras (ID@versi)",
    "Prompt overrides (JSON)": "gesaan gantian (JSON)",
    "Weight configuration (JSON)": "berat konfigurasi (JSON)",
    "Description": "penerangan",
    "Save suite": "simpan set",
    "Benchmark registry": "penanda aras daftar",
    "Dataset cache": "set data cache",
    "No source URL": "tiada sumber URL",
    "Accept license": "terima lesen",
    "Download and verify": "muat turun dan sahkan",
    "Run preflight": "larian pra-semak",
    "Checking…": "menyemak…",
    "Preflight": "pra-semak",
    "Evaluation runs": "penilaian larian",
    "Inspect": "periksa",
    "Run cap": "larian had",
    "Pause": "jeda",
    "Resume": "sambung",
    "Clone": "klon",
    "Retry failed": "cuba lagi gagal",
    "Archive": "arkib",
    "Task queue": "tugas baris",
    "Workers": "pekerja",
    "Worker": "pekerja",
    "Task": "tugas",
    "Run": "larian",
    "Priority": "keutamaan",
    "Attempts": "percubaan",
    "Created": "dicipta",
    "Run A": "larian satu",
    "Select completed run": "pilih selesai larian",
    "Compare": "bandingkan",
    "Report type": "laporan jenis",
    "Prompt comparison": "gesaan perbandingan",
    "Cost": "kos",
    "Related completed run": "berkaitan selesai larian",
    "Select run": "pilih larian",
    "Generate PDF": "jana PDF",
    "Generate JSON": "jana JSON",
    "Create user": "cipta pengguna",
    "Email": "e-mel",
    "Reviewer": "penyemak",
    "User concurrency cap": "pengguna serentak had",
    "Action": "tindakan",
    "Database": "pangkalan data",
    "Health": "kesihatan",
    "Queue": "baris",
    "Disk": "cakera",
    "Theme": "tema",
    "Workspace language": "ruang kerja bahasa",
    "Media preview": "media pratonton",
    "Loading": "memuatkan",
    "evidence…": "bukti…",
    "Audio preview unavailable.": "audio pratonton tidak tersedia.",
    "Video preview unavailable.": "video pratonton tidak tersedia.",
    "Download attached file": "muat turun dilampirkan fail",
    "Sample evidence": "sampel bukti",
    "Search samples": "cari sampel",
    "All states": "semua keadaan",
    "Succeeded": "berjaya",
    "Failed": "gagal",
    "Pending": "menunggu",
    "Running": "berjalan",
    "Correctness": "ketepatan",
    "Correct": "betul",
    "Incorrect": "salah",
    "Capability": "keupayaan",
    "Modality": "modaliti",
    "Language": "bahasa",
    "Difficulty": "kesukaran",
    "Error type": "ralat jenis",
    "Any error": "mana-mana ralat",
    "API error": "API ralat",
    "Parser error": "penghurai ralat",
    "Judge": "penilai",
    "Disagreement": "ketidaksetujuan",
    "No disagreement": "tiada ketidaksetujuan",
    "None": "tiada",
    "Load next 100 samples": "muatkan seterusnya 100 sampel",
    "Run executive summary": "larian eksekutif ringkasan",
    "Completion": "penyiapan",
    "Accuracy": "ketepatan",
    "Latency": "kependaman",
    "Loading summary...": "memuatkan ringkasan...",
    "Durable run log": "kekal larian log",
    "Capability evidence": "keupayaan bukti",
    "Score": "skor",
    "Samples": "sampel",
    "Run signals": "larian isyarat",
    "Loading next page…": "memuatkan seterusnya halaman…",
    "Reviewer ID": "penyemak ID",
    "Save review": "simpan semakan",
    "Judge evidence": "penilai bukti",
    "Baseline run": "garis asas larian",
    "No baseline": "tiada garis asas",
    "Row": "baris",
    "Column": "lajur",
    "Baseline / Δ": "garis asas / Δ",
    "Errors": "ralat",
    "Latency difference": "kependaman perbezaan",
    "Cost difference": "kos perbezaan",
    "Output tokens": "output token",
    "Stored encrypted": "disimpan disulitkan",
    "Unlimited": "tanpa had",
    "production, vision": "pengeluaran, penglihatan",
    "configured": "dikonfigurasikan",
    "cost not configured": "kos tidak dikonfigurasikan",
    "executed": "dilaksanakan",
    "paused": "dijeda",
    "resumed": "disambung",
    "cancelled": "dibatalkan",
    "single model": "tunggal model",
    "multi model": "berbilang model",
    "prompt comparison": "gesaan perbandingan",
    "Run {{action}}.": "larian {{action}}.",
    "{{dataset}} download paused.": "{{dataset}} muat turun dijeda.",
  },
};

for (const locale of localeIds) {
  Object.assign(phrases[locale], redesignedWorkspacePhrases[locale], localizationCompletionPhrases[locale], materializedStaticLabelPhrases[locale]);
}

const handAuthoredStaticPhraseTranslations: Partial<Record<Locale, readonly string[]>> = {
  "zh-CN": `默认请求正文（JSON）
新运行的提示词包
运行请求正文覆盖（JSON）
连接测试和执行使用已保存端点。运行覆盖会在套件和基准默认值之后合并；基准强制字段仍优先。API 密钥永不返回浏览器。
检测证据与用户声明保持分离。
探测能力前，请先添加模型端点。
尚未加载探测结果。
从工作区目录创建套件。
少样本示例（JSON 数组）
本地文件请使用数据集上传功能。
输入字段
参考（输出）字段
自定义多模态快速检查
请先上传资源。
文件会通过 MIME 签名验证、按内容寻址，并在进入运行快照前存储在浏览器内存之外。
选择图像、音频、视频或 PDF
正在上传并验证资源…
套件默认请求正文（JSON）
尚未创建套件。
注册数据集版本以管理下载和许可证。
在不创建队列条目的情况下验证兼容性并估算工作量。
验证模型端点后即可创建首个运行。
设置上限
执行
重新运行基准测试
没有排队工作。
实时更新从工作器事件通道传送。
没有活动工作器租约。
状态
租约到期
父级
模型和运行比较
运行必须使用相同的基准测试版本。差异按运行 A 减去运行 B 计算。
运行 B
报告
为以下对象生成可移植报告
，或下载以前的工件。
单模型完整报告
多模型比较
回归
可靠性
生成 HTML
生成 Markdown
生成 CSV
生成 Parquet
在“运行”页面选择一个运行后再生成报告。
审核者评分与确定性证据和评审证据保持分离。
从“运行”页面选择一个运行和样本以进行审核。
角色
查看者
评估者
管理员
创建 API 令牌用户
用户和审计追踪
服务器身份验证启用时，用户管理需要管理员持有者令牌。
最近的审计事件
实体
时间
运行时设置通过部署环境配置；敏感值绝不会返回浏览器。
架构版本
管理员或用户持有者令牌
保存令牌
清除令牌
SQLite 运行指南
SQLite 适用于本地或小型团队使用。对于多进程、分布式工作器部署，请使用 PostgreSQL 或 MongoDB；通过部署环境设置配置全局工作器上限。
切换到
模式
仅在选择此样本后获取。
此运行尚无已保存尝试。
异常
没有样本匹配这些筛选条件。
随实时运行事件刷新
尚未记录任务或样本生命周期事件。
尚无已评分能力证据。
未检测到显著异常或回归。
加载下一页证据
审核阶段
初审
复审
裁决
评分细则（JSON）
标签（逗号分隔）
此操作会记录针对所有已保存初审和复审的最终决定。
审核一致性
打开样本以加载审核一致性。
已保存审核
尚未为此尝试保存人工审核。
大语言模型评审
独立评审端点
请求评审判断
尚未记录独立评审判断。
报告工件
盲测成对评审
模型身份永不发送给评审器。
与匹配的样本尝试进行比较
单答案评审判断
或粘贴样本尝试 ID
运行反序交换测试
运行盲测比较
评审一致性
打开样本以加载评审一致性。
分析热图
每个单元格均保留其样本数、95% 置信区间、延迟、成本和可选基线差异。
交互式能力图表
单击条形图或按 Enter 键以检查模型能力结果。
完成运行以填充交互式评分条。
完成运行以填充此分析。
样本 / 95% 置信区间
仅 A 正确
仅 B 正确
指标
成功率
P95 延迟
我的本地模型
可用于本地 Ollama 服务
使用端点容量
样本、预测、错误
无法连接到评测服务。
能力探测会向此提供商发送少量请求，可能产生 API 费用。是否继续？
删除 {{dataset}} v{{version}} 的缓存数据？已注册版本将保留。
7 个步骤
注册模型端点和数据集，然后将评测运行加入队列并检查证据。
模型 · 配置提供商、运行连接测试并确认其可用。
数据集 · 声明来源，并可选设置输入和参考字段。
下载数据集并等待其状态就绪。
工作区 · 编写用户模板；记录字段通过 {{ placeholders }} 渲染。
运行盲测成对评审、保存人工审核并生成报告。
端点已保存。开始运行前请测试其连接。
能力探测已完成。声明的能力设置未更改。
用户能力声明已与检测证据一同保存。
预检已就绪：{{samples}} 个样本、{{requests}} 个请求、预计 {{tokens}} 个令牌、{{cost}}。
预检已阻止：{{issues}}
{{benchmark}} 已加入队列，并带有不可变配置快照。
已克隆运行，并生成新的不可变配置快照。
已将基准测试重新运行加入队列，并关联其源运行。
失败样本已作为新尝试加入队列。
运行已归档。其证据会一直通过 API 提供，直至删除。
未来任务认领的运行并发上限已更新；其评测快照保持不变。
{{benchmark}} 当前为 {{status}}。
已生成 {{format}} {{reportType}} 报告。
只读共享链接（{{expires}} 到期）：{{url}}
已保存版本化提示词包。
数据集版本已注册。
用户已创建。请立即复制此 API 令牌：{{token}}
已保存版本化评测套件。
已将 {{count}} 个套件运行加入队列。
已上传并选择经验证的媒体资源用于自定义运行。
请先选择可用端点并上传或选择媒体资源。
自定义多模态运行已加入队列，并带有不可变资源快照。
已接受许可证。现在可以下载数据集。
数据集已下载、验证并缓存。
数据集上传校验和已验证并存储在本地数据集缓存中。
已验证数据集缓存的校验和和大小。
已移除数据集缓存。您可以再次下载或上传它。
从同一基准测试版本中选择两个不同的运行。
人工审核已与自动结果分开保存。
已保存盲测成对评审证据和交换测试结果。
已保存独立 LLM 评审判断及理由证据。
任务优先级已更新为 {{priority}}。`.split("\n"),
  fr: `Corps de requête par défaut (JSON)
Paquet de prompts pour une nouvelle exécution
Remplacement du corps de requête de l’exécution (JSON)
Les tests de connexion et l’exécution utilisent le point de terminaison enregistré. Le remplacement de l’exécution est fusionné après les valeurs par défaut de la suite et du benchmark ; les champs imposés par le benchmark restent prioritaires. Les clés API ne reviennent jamais dans le navigateur.
Les preuves de détection et les déclarations des utilisateurs restent distinctes.
Ajoutez un point de terminaison de modèle avant de sonder les capacités.
Aucun résultat de sondage n’est encore chargé.
Créez une suite depuis le catalogue de l’espace de travail.
Exemples few-shot (tableau JSON)
Utilisez l’action de téléversement de jeu de données pour les fichiers locaux.
Champ d’entrée
Champ de référence (sortie)
Vérification rapide multimodale personnalisée
Téléversez d’abord une ressource.
Les fichiers sont validés par signature MIME, adressés par contenu et stockés hors de la mémoire du navigateur avant d’entrer dans un snapshot d’exécution.
Choisissez une image, un audio, une vidéo ou un PDF
Téléversement et validation de la ressource…
Corps de requête par défaut de la suite (JSON)
Aucune suite n’a été créée.
Enregistrez une version de jeu de données pour gérer les téléchargements et les licences.
Validez la compatibilité et estimez le travail sans créer d’entrée dans la file.
Vérifiez un point de terminaison de modèle pour créer la première exécution.
Définir le plafond
Exécuter
Relancer le benchmark
Aucun travail en file n’existe.
Les mises à jour en direct sont diffusées depuis le canal d’événements des workers.
Aucun bail de worker n’est actif.
État
Expiration du bail
Parent
Comparaison de modèles et d’exécutions
Les exécutions doivent utiliser la même version de benchmark. Les différences correspondent à l’exécution A moins l’exécution B.
Exécution B
Rapports
Générer un rapport portable pour
, ou téléchargez les artefacts précédents.
Complet pour un modèle
Comparaison de plusieurs modèles
Régression
Fiabilité
Générer HTML
Générer Markdown
Générer CSV
Générer Parquet
Choisissez une exécution dans la page Exécutions avant de générer un rapport.
Les scores des réviseurs restent distincts des preuves déterministes et des preuves de juge.
Sélectionnez une exécution et un échantillon depuis la page Exécutions pour les examiner.
Rôle
Lecteur
Évaluateur
Administrateur
Créer un utilisateur avec jeton API
Utilisateurs et piste d’audit
L’administration des utilisateurs nécessite un jeton porteur d’administrateur lorsque l’authentification du serveur est activée.
Événements d’audit récents
Entité
Quand
Les paramètres d’exécution sont configurés par l’environnement de déploiement ; les valeurs sensibles ne reviennent jamais dans le navigateur.
Version du schéma
Jeton porteur d’administrateur ou d’utilisateur
Enregistrer le jeton
Effacer le jeton
Guide d’exploitation SQLite
SQLite convient à une utilisation locale ou en petite équipe. Utilisez PostgreSQL ou MongoDB pour les déploiements de workers distribués à plusieurs processus ; configurez les plafonds globaux de workers avec les paramètres de l’environnement de déploiement.
Passer au
mode
Récupéré uniquement après la sélection de cet échantillon.
Cette exécution ne possède encore aucune tentative enregistrée.
Anomalie
Aucun échantillon ne correspond à ces filtres.
Actualisé avec les événements d’exécution en direct
Aucun événement de cycle de vie de tâche ou d’échantillon n’a été enregistré.
Pas encore de preuve de capacité notée.
Aucune anomalie ni régression significative détectée.
Charger la page de preuves suivante
Étape de révision
Révision principale
Révision secondaire
Arbitrage
Grille d’évaluation (JSON)
Libellés (séparés par des virgules)
Cette action enregistre une décision finale sur toutes les révisions principales et secondaires sauvegardées.
Accord de révision
Ouvrez un échantillon pour charger l’accord de révision.
Révisions enregistrées
Aucune révision humaine n’a été enregistrée pour cette tentative.
LLM en tant que juge
Point de terminaison de juge indépendant
Demander l’évaluation du juge
Aucune évaluation de juge indépendant n’a été enregistrée.
Artefacts de rapport
Juge pair-à-pair en aveugle
Les identités des modèles ne sont jamais envoyées au juge.
Comparer avec la tentative d’échantillon correspondante
Évaluation du juge pour une seule réponse
Ou collez un ID de tentative d’échantillon
Exécuter le test d’inversion de l’ordre
Exécuter la comparaison en aveugle
Accord du juge
Ouvrez un échantillon pour charger l’accord du juge.
Cartes thermiques d’analyse
Chaque cellule conserve son nombre d’échantillons, son intervalle de confiance à 95 %, sa latence, son coût et son delta de référence facultatif.
Graphique interactif des capacités
Cliquez sur une barre ou utilisez Entrée pour examiner le résultat modèle-capacité fourni.
Terminez une exécution pour remplir les barres de score interactives.
Terminez des exécutions pour remplir cette analyse.
Échantillons / IC à 95 %
Correct uniquement pour A
Correct uniquement pour B
Métrique
Taux de réussite
Latence P95
Mon modèle local
Facultatif pour un service Ollama local
Utiliser la capacité du point de terminaison
échantillon, prédiction, erreur
Impossible d’atteindre le service d’évaluation.
Le sondage des capacités envoie de petites requêtes à ce fournisseur et peut entraîner des frais d’API. Continuer ?
Supprimer les données mises en cache pour {{dataset}} v{{version}} ? La version enregistrée restera disponible.
7 étapes
Enregistrez un point de terminaison de modèle et un jeu de données, puis mettez des exécutions d’évaluation en file et examinez les preuves.
Modèles · configurez le fournisseur, exécutez un test de connexion et confirmez sa disponibilité.
Jeux de données · déclarez la source et, éventuellement, les champs d’entrée et de référence.
Téléchargez le jeu de données et attendez que son état soit prêt.
Espace de travail · rédigez le modèle utilisateur ; les champs d’enregistrement sont rendus via {{ placeholders }}.
Exécutez un jugement pair-à-pair en aveugle, enregistrez les révisions humaines et générez des rapports.
Point de terminaison enregistré. Testez sa connexion avant de démarrer une exécution.
Sondage des capacités terminé. Les paramètres de capacité déclarés n’ont pas été modifiés.
La déclaration de capacité utilisateur a été enregistrée avec les preuves de détection.
Précontrôle prêt : {{samples}} échantillons, {{requests}} requêtes, {{tokens}} jetons estimés, {{cost}}.
Précontrôle bloqué : {{issues}}
{{benchmark}} a été mis en file avec un snapshot de configuration immuable.
Exécution clonée avec un nouveau snapshot de configuration immuable.
Nouvelle exécution du benchmark mise en file avec un lien vers son exécution source.
Les échantillons échoués ont été mis en file comme nouvelles tentatives.
Exécution archivée. Ses preuves restent accessibles par l’API jusqu’à leur suppression.
Le plafond de concurrence de l’exécution a été mis à jour pour les prochaines acquisitions de tâche ; son snapshot d’évaluation reste inchangé.
{{benchmark}} est maintenant {{status}}.
Rapport {{reportType}} au format {{format}} généré.
Lien de partage en lecture seule (expire {{expires}}) : {{url}}
Paquet de prompts versionné enregistré.
Version du jeu de données enregistrée.
Utilisateur créé. Copiez ce jeton API maintenant : {{token}}
Suite d’évaluation versionnée enregistrée.
{{count}} exécution(s) de suite mise(s) en file.
Ressource multimédia validée téléversée et sélectionnée pour l’exécution personnalisée.
Sélectionnez d’abord un point de terminaison disponible, puis téléversez ou choisissez une ressource multimédia.
Exécution multimodale personnalisée mise en file avec un snapshot de ressource immuable.
Licence acceptée. Le jeu de données peut maintenant être téléchargé.
Jeu de données téléchargé, vérifié et mis en cache.
La somme de contrôle du téléversement du jeu de données a été vérifiée et stockée dans le cache local.
La somme de contrôle et la taille du cache du jeu de données ont été vérifiées.
Cache du jeu de données supprimé. Vous pouvez le télécharger ou le téléverser à nouveau.
Choisissez deux exécutions différentes de la même version de benchmark.
La révision humaine a été enregistrée séparément des résultats automatisés.
Les preuves du juge pair-à-pair en aveugle et les résultats du test d’inversion ont été enregistrés.
L’évaluation indépendante LLM en tant que juge a été enregistrée avec les preuves de justification.
La priorité de la tâche a été mise à jour à {{priority}}.`.split("\n"),
  de: `Standard-Anfragetext (JSON)
Prompt-Paket für einen neuen Lauf
Überschreibung des Anfragetexts für den Lauf (JSON)
Verbindungstests und Ausführung verwenden den gespeicherten Endpunkt. Die Laufüberschreibung wird nach den Standardwerten der Suite und des Benchmarks zusammengeführt; vom Benchmark erzwungene Felder behalten Vorrang. API-Schlüssel werden nie an den Browser zurückgegeben.
Erkennungsnachweise und Benutzerdeklarationen bleiben getrennt.
Fügen Sie einen Modellendpunkt hinzu, bevor Sie Funktionen prüfen.
Noch kein Prüfergebnis geladen.
Erstellen Sie eine Suite aus dem Arbeitsbereichskatalog.
Few-Shot-Beispiele (JSON-Array)
Verwenden Sie für lokale Dateien die Aktion zum Hochladen eines Datensatzes.
Eingabefeld
Referenzfeld (Ausgabe)
Benutzerdefinierte multimodale Schnellprüfung
Laden Sie zuerst ein Asset hoch.
Dateien werden anhand ihrer MIME-Signatur validiert, inhaltsadressiert und außerhalb des Browserspeichers abgelegt, bevor sie in einen Laufschnappschuss gelangen.
Wählen Sie Bild, Audio, Video oder PDF
Asset wird hochgeladen und validiert…
Standard-Anfragetext der Suite (JSON)
Es wurden noch keine Suiten erstellt.
Registrieren Sie eine Datensatzversion, um Downloads und Lizenzen zu verwalten.
Validieren Sie die Kompatibilität und schätzen Sie den Aufwand, ohne einen Warteschlangeneintrag zu erstellen.
Prüfen Sie einen Modellendpunkt, um den ersten Lauf zu erstellen.
Obergrenze festlegen
Ausführen
Benchmark erneut ausführen
Es gibt keine eingereihten Aufgaben.
Live-Updates werden über den Worker-Ereigniskanal gestreamt.
Keine Worker-Leases sind aktiv.
Status
Ablauf des Leases
Übergeordnet
Modell- und Laufvergleich
Läufe müssen dieselbe Benchmark-Version verwenden. Unterschiede entsprechen Lauf A minus Lauf B.
Lauf B
Berichte
Portablen Bericht erstellen für
, oder laden Sie frühere Artefakte herunter.
Vollständig für ein Modell
Vergleich mehrerer Modelle
Regression
Zuverlässigkeit
HTML generieren
Markdown generieren
CSV generieren
Parquet generieren
Wählen Sie auf der Seite Läufe einen Lauf aus, bevor Sie einen Bericht generieren.
Prüferbewertungen bleiben von deterministischen Nachweisen und Richternachweisen getrennt.
Wählen Sie auf der Seite Läufe einen Lauf und eine Stichprobe zur Überprüfung aus.
Rolle
Betrachter
Evaluator
Administrator
API-Token-Benutzer erstellen
Benutzer und Prüfprotokoll
Die Benutzerverwaltung benötigt ein Administrator-Bearer-Token, wenn die Serverauthentifizierung aktiviert ist.
Neueste Prüfereignisse
Entität
Zeitpunkt
Laufzeiteinstellungen werden über die Bereitstellungsumgebung konfiguriert; vertrauliche Werte werden nie an den Browser zurückgegeben.
Schemaversion
Administrator- oder Benutzer-Bearer-Token
Token speichern
Token löschen
SQLite-Betriebshinweise
SQLite eignet sich für lokale Nutzung oder kleine Teams. Verwenden Sie PostgreSQL oder MongoDB für Mehrprozess- und verteilte Worker-Bereitstellungen; konfigurieren Sie globale Worker-Obergrenzen über Einstellungen der Bereitstellungsumgebung.
Wechseln zu
Modus
Wird erst abgerufen, nachdem diese Stichprobe ausgewählt wurde.
Dieser Lauf hat noch keine gespeicherten Versuche.
Anomalie
Keine Stichproben entsprechen diesen Filtern.
Wird mit Live-Laufereignissen aktualisiert
Es wurden keine Lebenszyklusereignisse für Aufgaben oder Stichproben aufgezeichnet.
Noch keine bewerteten Fähigkeitsnachweise.
Keine signifikanten Anomalien oder Regressionen erkannt.
Nächste Nachweisseite laden
Überprüfungsphase
Primäre Überprüfung
Sekundäre Überprüfung
Entscheidung
Bewertungsraster (JSON)
Beschriftungen (durch Kommas getrennt)
Dies erfasst eine endgültige Entscheidung über alle gespeicherten primären und sekundären Überprüfungen.
Übereinstimmung der Überprüfung
Öffnen Sie eine Stichprobe, um die Überprüfungsübereinstimmung zu laden.
Gespeicherte Überprüfungen
Für diesen Versuch wurde keine menschliche Überprüfung gespeichert.
LLM als Richter
Unabhängiger Richterendpunkt
Richterbewertung anfordern
Es wurde keine unabhängige Richterbewertung aufgezeichnet.
Berichtsartefakte
Verblindeter paarweiser Richter
Modellidentitäten werden nie an den Richter gesendet.
Mit passendem Stichprobenversuch vergleichen
Richterbewertung für eine einzelne Antwort
Oder eine Stichprobenversuchs-ID einfügen
Test zum Umkehren der Reihenfolge ausführen
Verblindeten Vergleich ausführen
Richterübereinstimmung
Öffnen Sie eine Stichprobe, um die Richterübereinstimmung zu laden.
Analyse-Heatmaps
Jede Zelle enthält ihre Stichprobenzahl, ihr 95%-Konfidenzintervall, ihre Latenz, ihre Kosten und eine optionale Basisliniendifferenz.
Interaktives Fähigkeitsdiagramm
Klicken Sie auf einen Balken oder drücken Sie die Eingabetaste, um das Modellfähigkeitsresultat zu prüfen.
Schließen Sie einen Lauf ab, um interaktive Ergebnisbalken zu füllen.
Schließen Sie Läufe ab, um diese Analyse zu füllen.
Stichproben / 95%-KI
Nur A korrekt
Nur B korrekt
Metrik
Erfolgsrate
P95-Latenz
Mein lokales Modell
Optional für einen lokalen Ollama-Dienst
Endpunktkapazität verwenden
Stichprobe, Vorhersage, Fehler
Der Bewertungsdienst ist nicht erreichbar.
Die Funktionsprüfung sendet kleine Anfragen an diesen Anbieter und kann API-Kosten verursachen. Fortfahren?
Die zwischengespeicherten Daten für {{dataset}} v{{version}} entfernen? Die registrierte Version bleibt erhalten.
7 Schritte
Registrieren Sie einen Modellendpunkt und einen Datensatz, reihen Sie dann Bewertungsläufe ein und prüfen Sie die Nachweise.
Modelle · konfigurieren Sie den Anbieter, führen Sie einen Verbindungstest durch und bestätigen Sie die Verfügbarkeit.
Datensätze · geben Sie die Quelle sowie optional die Eingabe- und Referenzfelder an.
Laden Sie den Datensatz herunter und warten Sie, bis sein Status bereit ist.
Arbeitsbereich · schreiben Sie die Benutzervorlage; Datensatzfelder werden über {{ placeholders }} gerendert.
Führen Sie verblindete paarweise Bewertungen aus, speichern Sie menschliche Überprüfungen und generieren Sie Berichte.
Endpunkt gespeichert. Testen Sie seine Verbindung, bevor Sie einen Lauf starten.
Funktionsprüfung abgeschlossen. Deklarierte Fähigkeitseinstellungen wurden nicht geändert.
Die Benutzer-Fähigkeitsdeklaration wurde zusammen mit den Erkennungsnachweisen gespeichert.
Vorprüfung bereit: {{samples}} Stichproben, {{requests}} Anfragen, {{tokens}} geschätzte Token, {{cost}}.
Vorprüfung blockiert: {{issues}}
{{benchmark}} wurde mit einem unveränderlichen Konfigurationsschnappschuss eingereiht.
Lauf mit einem neuen unveränderlichen Konfigurationsschnappschuss geklont.
Benchmark-Neuausführung wurde mit einem Link zu ihrem Ursprungslauf eingereiht.
Fehlgeschlagene Stichproben wurden als neue Versuche eingereiht.
Lauf archiviert. Seine Nachweise bleiben über die API verfügbar, bis sie gelöscht werden.
Die Lauf-Obergrenze wurde für zukünftige Aufgabenübernahmen aktualisiert; sein Bewertungsschnappschuss bleibt unverändert.
{{benchmark}} ist jetzt {{status}}.
{{format}}-{{reportType}}-Bericht generiert.
Schreibgeschützter Freigabelink (läuft {{expires}} ab): {{url}}
Versioniertes Prompt-Paket gespeichert.
Datensatzversion registriert.
Benutzer erstellt. Kopieren Sie dieses API-Token jetzt: {{token}}
Versionierte Bewertungssuite gespeichert.
{{count}} Suite-Lauf/Läufe eingereiht.
Validiertes Medien-Asset wurde hochgeladen und für den benutzerdefinierten Lauf ausgewählt.
Wählen Sie zuerst einen verfügbaren Endpunkt und laden Sie ein Medien-Asset hoch oder wählen Sie eines aus.
Benutzerdefinierter multimodaler Lauf mit unveränderlichem Asset-Schnappschuss eingereiht.
Lizenz akzeptiert. Der Datensatz kann jetzt heruntergeladen werden.
Datensatz heruntergeladen, verifiziert und zwischengespeichert.
Die Prüfsumme des Datensatzuploads wurde verifiziert und im lokalen Datensatzcache gespeichert.
Prüfsumme und Größe des Datensatzcaches wurden verifiziert.
Datensatzcache entfernt. Sie können ihn erneut herunterladen oder hochladen.
Wählen Sie zwei verschiedene Läufe derselben Benchmark-Version aus.
Menschliche Überprüfung wurde getrennt von automatisierten Ergebnissen gespeichert.
Nachweise des verblindeten paarweisen Richters und Ergebnisse des Umkehrtests wurden gespeichert.
Unabhängige LLM-als-Richter-Bewertung wurde mit Begründungsnachweisen gespeichert.
Aufgabenpriorität auf {{priority}} aktualisiert.`.split("\n"),
  ru: `Тело запроса по умолчанию (JSON)
Пакет промптов для нового запуска
Переопределение тела запроса запуска (JSON)
Проверки подключения и выполнение используют сохранённую конечную точку. Переопределение запуска объединяется после значений по умолчанию набора и бенчмарка; поля, принудительно заданные бенчмарком, по-прежнему имеют приоритет. Ключи API никогда не возвращаются в браузер.
Доказательства обнаружения и декларации пользователей остаются раздельными.
Добавьте конечную точку модели перед проверкой возможностей.
Результат проверки ещё не загружен.
Создайте набор из каталога рабочего пространства.
Примеры few-shot (массив JSON)
Используйте действие загрузки набора данных для локальных файлов.
Поле ввода
Поле эталонного ответа (вывод)
Пользовательская быстрая мультимодальная проверка
Сначала загрузите ресурс.
Файлы проверяются по MIME-подписи, адресуются по содержимому и хранятся вне памяти браузера до попадания в снимок запуска.
Выберите изображение, аудио, видео или PDF
Загрузка и проверка ресурса…
Тело запроса набора по умолчанию (JSON)
Наборы ещё не созданы.
Зарегистрируйте версию набора данных для управления загрузками и лицензиями.
Проверьте совместимость и оцените объём работы без создания записи в очереди.
Проверьте конечную точку модели, чтобы создать первый запуск.
Установить ограничение
Выполнить
Перезапустить бенчмарк
В очереди нет заданий.
Обновления в реальном времени передаются из канала событий воркеров.
Нет активных аренд воркеров.
Состояние
Истечение аренды
Родительский объект
Сравнение модели и запуска
Запуски должны использовать одну версию бенчмарка. Разница рассчитывается как запуск A минус запуск B.
Запуск B
Отчёты
Создать переносимый отчёт для
, или скачайте предыдущие артефакты.
Полный для одной модели
Сравнение нескольких моделей
Регрессия
Надёжность
Создать HTML
Создать Markdown
Создать CSV
Создать Parquet
Перед созданием отчёта выберите запуск на странице «Запуски».
Оценки рецензентов остаются отдельными от детерминированных доказательств и доказательств судьи.
Выберите запуск и образец на странице «Запуски», чтобы проверить их.
Роль
Наблюдатель
Оценщик
Администратор
Создать пользователя с API-токеном
Пользователи и журнал аудита
Для управления пользователями требуется токен носителя администратора, когда включена аутентификация сервера.
Недавние события аудита
Сущность
Когда
Параметры выполнения задаются через среду развёртывания; чувствительные значения никогда не возвращаются в браузер.
Версия схемы
Токен носителя администратора или пользователя
Сохранить токен
Очистить токен
Руководство по эксплуатации SQLite
SQLite подходит для локального использования или небольшой команды. Используйте PostgreSQL или MongoDB для многопроцессных и распределённых развёртываний воркеров; настройте глобальные ограничения воркеров с помощью параметров среды развёртывания.
Переключиться в
режим
Получается только после выбора этого образца.
У этого запуска ещё нет сохранённых попыток.
Аномалия
Ни один образец не соответствует этим фильтрам.
Обновляется событиями запуска в реальном времени
События жизненного цикла задач или образцов не записаны.
Оценённых доказательств возможностей пока нет.
Значимых аномалий или регрессий не обнаружено.
Загрузить следующую страницу доказательств
Этап проверки
Первичная проверка
Вторичная проверка
Разрешение разногласий
Рубрика (JSON)
Метки (через запятую)
Это фиксирует окончательное решение по всем сохранённым первичным и вторичным проверкам.
Согласие проверки
Откройте образец, чтобы загрузить согласие проверки.
Сохранённые проверки
Для этой попытки не сохранена проверка человеком.
LLM в роли судьи
Независимая конечная точка судьи
Запросить оценку судьи
Независимая оценка судьи ещё не записана.
Артефакты отчёта
Слепой попарный судья
Идентификаторы моделей никогда не отправляются судье.
Сравнить с соответствующей попыткой образца
Оценка судьи для одного ответа
Или вставьте ID попытки образца
Запустить тест смены порядка
Запустить слепое сравнение
Согласие судьи
Откройте образец, чтобы загрузить согласие судьи.
Тепловые карты анализа
В каждой ячейке сохраняются число образцов, 95%-й доверительный интервал, задержка, стоимость и необязательная разница с базовой линией.
Интерактивная диаграмма возможностей
Щёлкните столбец или нажмите Enter, чтобы проверить результат для модели и возможности.
Завершите запуск, чтобы заполнить интерактивные столбцы оценок.
Завершите запуски, чтобы заполнить этот анализ.
Образцы / 95% ДИ
Верно только для A
Верно только для B
Метрика
Доля успеха
Задержка P95
Моя локальная модель
Необязательно для локальной службы Ollama
Использовать ёмкость конечной точки
образец, прогноз, ошибка
Не удаётся подключиться к службе оценки.
Проверка возможностей отправляет небольшие запросы этому поставщику и может повлечь расходы на API. Продолжить?
Удалить кэшированные данные для {{dataset}} v{{version}}? Зарегистрированная версия останется.
7 шагов
Зарегистрируйте конечную точку модели и набор данных, затем поставьте запуски оценки в очередь и изучите доказательства.
Модели · настройте поставщика, выполните проверку подключения и подтвердите доступность.
Наборы данных · укажите источник, а также при необходимости поля ввода и эталонного ответа.
Скачайте набор данных и дождитесь состояния готовности.
Рабочее пространство · напишите пользовательский шаблон; поля записи отображаются через {{ placeholders }}.
Запустите слепое попарное судейство, сохраните проверки человеком и создайте отчёты.
Конечная точка сохранена. Проверьте её подключение перед началом запуска.
Проверка возможностей завершена. Заявленные параметры возможностей не изменены.
Декларация возможностей пользователя сохранена вместе с доказательствами обнаружения.
Предварительная проверка готова: {{samples}} образцов, {{requests}} запросов, {{tokens}} расчётных токенов, {{cost}}.
Предварительная проверка заблокирована: {{issues}}
{{benchmark}} поставлен в очередь с неизменяемым снимком конфигурации.
Запуск клонирован с новым неизменяемым снимком конфигурации.
Повторный запуск бенчмарка поставлен в очередь со ссылкой на исходный запуск.
Неудачные образцы поставлены в очередь как новые попытки.
Запуск архивирован. Его доказательства доступны через API до удаления.
Ограничение параллелизма запуска обновлено для будущих получений задач; его снимок оценки не изменился.
{{benchmark}} теперь {{status}}.
Создан {{reportType}}-отчёт в формате {{format}}.
Ссылка только для чтения (истекает {{expires}}): {{url}}
Версионированный пакет промптов сохранён.
Версия набора данных зарегистрирована.
Пользователь создан. Скопируйте этот API-токен сейчас: {{token}}
Версионированный набор оценки сохранён.
{{count}} запуск(ов) набора поставлено в очередь.
Проверенный медиафайл загружен и выбран для пользовательского запуска.
Сначала выберите доступную конечную точку и загрузите или выберите медиафайл.
Пользовательский мультимодальный запуск поставлен в очередь с неизменяемым снимком ресурса.
Лицензия принята. Набор данных теперь можно скачать.
Набор данных скачан, проверен и кэширован.
Контрольная сумма загрузки набора данных проверена и сохранена в локальном кэше набора данных.
Контрольная сумма и размер кэша набора данных проверены.
Кэш набора данных удалён. Его можно скачать или загрузить снова.
Выберите два разных запуска одной версии бенчмарка.
Проверка человеком сохранена отдельно от автоматизированных результатов.
Доказательства слепого попарного судьи и результаты теста смены порядка сохранены.
Независимая оценка LLM в роли судьи сохранена с доказательствами обоснования.
Приоритет задачи обновлён до {{priority}}.`.split("\n"),
  ja: `既定のリクエスト本文（JSON）
新しい実行用のプロンプト パッケージ
実行リクエスト本文のオーバーライド（JSON）
接続テストと実行では保存済みエンドポイントを使用します。実行のオーバーライドはスイートとベンチマークの既定値の後にマージされ、ベンチマークで強制されるフィールドは引き続き優先されます。API キーがブラウザに返されることはありません。
検出証拠とユーザー宣言は分けて保持されます。
機能をプローブする前にモデル エンドポイントを追加してください。
まだプローブ結果は読み込まれていません。
ワークスペース カタログからスイートを作成します。
Few-shot の例（JSON 配列）
ローカル ファイルにはデータセットのアップロード操作を使用してください。
入力フィールド
参照（出力）フィールド
カスタム マルチモーダル クイックチェック
最初にアセットをアップロードしてください。
ファイルは MIME シグネチャで検証され、コンテンツアドレス化され、実行スナップショットに入る前にブラウザ メモリ外に保存されます。
画像、音声、動画、または PDF を選択
アセットをアップロードして検証中…
スイートの既定のリクエスト本文（JSON）
まだスイートは作成されていません。
ダウンロードとライセンスを管理するためにデータセット バージョンを登録します。
キュー項目を作成せずに互換性を検証し、作業量を見積もります。
最初の実行を作成する前にモデル エンドポイントを検証してください。
上限を設定
実行
ベンチマークを再実行
キューに入っている作業はありません。
ライブ更新はワーカー イベント チャネルからストリーミングされます。
アクティブなワーカー リースはありません。
状態
リースの有効期限
親
モデルと実行の比較
実行には同じベンチマーク バージョンを使用する必要があります。差分は常に実行 A から実行 B を引いて計算されます。
実行 B
レポート
次の対象のポータブル レポートを生成
、または以前の成果物をダウンロードします。
単一モデル完全版
複数モデル比較
回帰
信頼性
HTML を生成
Markdown を生成
CSV を生成
Parquet を生成
レポートを生成する前に、実行ページで実行を選択してください。
レビュアーのスコアは、決定論的な証拠および判定者の証拠とは分けて保持されます。
実行ページで実行とサンプルを選択してレビューします。
ロール
閲覧者
評価者
管理者
API トークン ユーザーを作成
ユーザーと監査証跡
サーバー認証が有効な場合、ユーザー管理には管理者ベアラー トークンが必要です。
最近の監査イベント
エンティティ
日時
ランタイム設定はデプロイ環境で構成され、機密値がブラウザに返されることはありません。
スキーマ バージョン
管理者またはユーザーのベアラー トークン
トークンを保存
トークンを消去
SQLite 運用ガイド
SQLite はローカルまたは小規模チームでの利用に適しています。マルチプロセスまたは分散ワーカーのデプロイには PostgreSQL または MongoDB を使用し、グローバル ワーカー上限はデプロイ環境設定で構成してください。
次に切り替える
モード
このサンプルを選択した後にのみ取得されます。
この実行にはまだ保存済みの試行がありません。
異常
これらのフィルターに一致するサンプルはありません。
ライブ実行イベントで更新されます
タスクまたはサンプルのライフサイクル イベントは記録されていません。
スコア付きの機能証拠はまだありません。
重大な異常または回帰は検出されませんでした。
次の証拠ページを読み込む
レビュー段階
一次レビュー
二次レビュー
裁定
評価基準（JSON）
ラベル（コンマ区切り）
これにより、保存済みのすべての一次・二次レビューに対する最終決定が記録されます。
レビューの一致
サンプルを開いてレビューの一致を読み込みます。
保存済みレビュー
この試行には人によるレビューが保存されていません。
LLM-as-a-judge
独立した判定者エンドポイント
判定者の評価をリクエスト
独立した判定者の評価は記録されていません。
レポート成果物
ブラインドのペアワイズ判定
モデルの識別情報が判定者に送信されることはありません。
一致するサンプル試行と比較
単一回答の判定者評価
またはサンプル試行 ID を貼り付け
逆順入れ替えテストを実行
ブラインド比較を実行
判定者の一致
サンプルを開いて判定者の一致を読み込みます。
分析ヒートマップ
各セルにはサンプル数、95% 信頼区間、レイテンシ、コスト、任意のベースライン差分が保持されます。
インタラクティブな機能グラフ
バーをクリックするか Enter キーを押して、モデル機能の結果を確認します。
実行を完了してインタラクティブなスコア バーを表示します。
実行を完了してこの分析を表示します。
サンプル / 95% 信頼区間
A のみ正解
B のみ正解
指標
成功率
P95 レイテンシ
ローカル モデル
ローカル Ollama サービスでは任意
エンドポイント容量を使用
サンプル、予測、エラー
評価サービスに接続できません。
機能プローブはこのプロバイダーに小さなリクエストを送信するため、API 料金が発生する場合があります。続行しますか？
{{dataset}} v{{version}} のキャッシュ データを削除しますか？登録済みバージョンは残ります。
7 ステップ
モデル エンドポイントとデータセットを登録し、評価実行をキューに入れて証拠を確認します。
モデル · プロバイダーを構成し、接続テストを実行して、利用可能であることを確認します。
データセット · ソースを宣言し、必要に応じて入力フィールドと参照フィールドを指定します。
データセットをダウンロードし、ステータスが準備完了になるまで待ちます。
ワークスペース · ユーザー テンプレートを作成します。レコード フィールドは {{ placeholders }} を通じてレンダリングされます。
ブラインドのペアワイズ判定を実行し、人によるレビューを保存してレポートを生成します。
エンドポイントを保存しました。実行を開始する前に接続をテストしてください。
機能プローブが完了しました。宣言済みの機能設定は変更されていません。
ユーザーの機能宣言は検出証拠とともに保存されました。
事前チェックの準備ができました: {{samples}} サンプル、{{requests}} リクエスト、推定 {{tokens}} トークン、{{cost}}。
事前チェックがブロックされました: {{issues}}
{{benchmark}} は不変の構成スナップショットとともにキューに入りました。
実行を新しい不変の構成スナップショットで複製しました。
ベンチマークの再実行は、元の実行へのリンクとともにキューに入りました。
失敗したサンプルは新しい試行としてキューに入りました。
実行をアーカイブしました。その証拠は削除されるまで API から利用できます。
実行の同時実行上限を今後のタスク取得用に更新しました。評価スナップショットは変更されません。
{{benchmark}} は現在 {{status}} です。
{{format}} の {{reportType}} レポートを生成しました。
読み取り専用の共有リンク（{{expires}} に期限切れ）: {{url}}
バージョン管理されたプロンプト パッケージを保存しました。
データセット バージョンを登録しました。
ユーザーを作成しました。この API トークンを今すぐコピーしてください: {{token}}
バージョン管理された評価スイートを保存しました。
{{count}} 件のスイート実行をキューに入れました。
検証済みのメディア アセットをアップロードし、カスタム実行用に選択しました。
最初に利用可能なエンドポイントを選択し、メディア アセットをアップロードまたは選択してください。
カスタム マルチモーダル実行を不変のアセット スナップショットとともにキューに入れました。
ライセンスを承諾しました。データセットをダウンロードできます。
データセットをダウンロード、検証し、キャッシュしました。
データセット アップロードのチェックサムを検証し、ローカル データセット キャッシュに保存しました。
データセット キャッシュのチェックサムとサイズを検証しました。
データセット キャッシュを削除しました。再度ダウンロードまたはアップロードできます。
同じベンチマーク バージョンから異なる 2 つの実行を選択します。
人によるレビューは自動結果とは別に保存されました。
ブラインドのペアワイズ判定の証拠と入れ替えテストの結果を保存しました。
根拠の証拠とともに独立した LLM-as-a-judge 評価を保存しました。
タスク優先度を {{priority}} に更新しました。`.split("\n"),
  ko: `기본 요청 본문(JSON)
새 실행용 프롬프트 패키지
실행 요청 본문 재정의(JSON)
연결 테스트와 실행은 저장된 엔드포인트를 사용합니다. 실행 재정의는 스위트 및 벤치마크 기본값 뒤에 병합되며 벤치마크에서 강제한 필드는 계속 우선합니다. API 키는 브라우저로 반환되지 않습니다.
감지 증거와 사용자 선언은 별도로 유지됩니다.
기능을 프로브하기 전에 모델 엔드포인트를 추가하세요.
아직 로드된 프로브 결과가 없습니다.
작업 공간 카탈로그에서 스위트를 만드세요.
퓨샷 예제(JSON 배열)
로컬 파일에는 데이터 세트 업로드 작업을 사용하세요.
입력 필드
참조(출력) 필드
사용자 지정 멀티모달 빠른 검사
먼저 자산을 업로드하세요.
파일은 MIME 서명으로 검증되고 콘텐츠 주소화되며 실행 스냅샷에 들어가기 전에 브라우저 메모리 밖에 저장됩니다.
이미지, 오디오, 비디오 또는 PDF 선택
자산 업로드 및 검증 중…
스위트 기본 요청 본문(JSON)
아직 만든 스위트가 없습니다.
다운로드와 라이선스를 관리하려면 데이터 세트 버전을 등록하세요.
대기열 항목을 만들지 않고 호환성을 검증하고 작업량을 추정하세요.
첫 실행을 만들려면 모델 엔드포인트를 검증하세요.
상한 설정
실행
벤치마크 다시 실행
대기 중인 작업이 없습니다.
실시간 업데이트는 워커 이벤트 채널에서 스트리밍됩니다.
활성 워커 임대가 없습니다.
상태
임대 만료
상위 항목
모델 및 실행 비교
실행은 같은 벤치마크 버전을 사용해야 합니다. 차이는 항상 실행 A에서 실행 B를 뺀 값입니다.
실행 B
보고서
다음에 대한 이동식 보고서 생성
, 또는 이전 아티팩트를 다운로드하세요.
단일 모델 전체
다중 모델 비교
회귀
신뢰성
HTML 생성
Markdown 생성
CSV 생성
Parquet 생성
보고서를 생성하기 전에 실행 페이지에서 실행을 선택하세요.
검토자 점수는 결정적 증거 및 판정자 증거와 별도로 유지됩니다.
실행 페이지에서 실행과 샘플을 선택하여 검토하세요.
역할
뷰어
평가자
관리자
API 토큰 사용자 만들기
사용자 및 감사 추적
서버 인증이 사용 설정된 경우 사용자 관리에는 관리자 베어러 토큰이 필요합니다.
최근 감사 이벤트
엔터티
시간
런타임 설정은 배포 환경에서 구성되며 민감한 값은 브라우저로 반환되지 않습니다.
스키마 버전
관리자 또는 사용자 베어러 토큰
토큰 저장
토큰 지우기
SQLite 운영 안내
SQLite는 로컬 또는 소규모 팀 사용에 적합합니다. 다중 프로세스 및 분산 워커 배포에는 PostgreSQL 또는 MongoDB를 사용하고 배포 환경 설정으로 전역 워커 상한을 구성하세요.
다음으로 전환
모드
이 샘플을 선택한 후에만 가져옵니다.
이 실행에는 아직 저장된 시도가 없습니다.
이상 징후
이 필터와 일치하는 샘플이 없습니다.
실시간 실행 이벤트로 새로 고침
작업 또는 샘플 수명 주기 이벤트가 기록되지 않았습니다.
아직 점수화된 기능 증거가 없습니다.
중요한 이상 징후 또는 회귀가 감지되지 않았습니다.
다음 증거 페이지 불러오기
검토 단계
기본 검토
보조 검토
판정
평가 기준(JSON)
레이블(쉼표로 구분)
저장된 모든 기본 및 보조 검토에 대한 최종 결정을 기록합니다.
검토 일치도
샘플을 열어 검토 일치도를 불러오세요.
저장된 검토
이 시도에는 사람 검토가 저장되지 않았습니다.
LLM 판정
독립 판정자 엔드포인트
판정자 평가 요청
독립 판정자 평가가 기록되지 않았습니다.
보고서 아티팩트
블라인드 쌍대 판정
모델 ID는 판정자에게 전송되지 않습니다.
일치하는 샘플 시도와 비교
단일 답변 판정자 평가
또는 샘플 시도 ID 붙여넣기
역순 교환 테스트 실행
블라인드 비교 실행
판정자 일치도
샘플을 열어 판정자 일치도를 불러오세요.
분석 히트맵
각 셀은 샘플 수, 95% 신뢰 구간, 지연 시간, 비용 및 선택적 기준선 차이를 유지합니다.
대화형 기능 차트
막대를 클릭하거나 Enter 키를 눌러 모델 기능 결과를 확인하세요.
실행을 완료하여 대화형 점수 막대를 채우세요.
실행을 완료하여 이 분석을 채우세요.
샘플 / 95% 신뢰 구간
A만 정답
B만 정답
측정항목
성공률
P95 지연 시간
내 로컬 모델
로컬 Ollama 서비스에 선택 사항
엔드포인트 용량 사용
샘플, 예측, 오류
평가 서비스에 연결할 수 없습니다.
기능 프로브는 이 공급자에 작은 요청을 보내며 API 요금이 발생할 수 있습니다. 계속할까요?
{{dataset}} v{{version}}의 캐시 데이터를 제거할까요? 등록된 버전은 유지됩니다.
7단계
모델 엔드포인트와 데이터 세트를 등록한 다음 평가 실행을 대기열에 넣고 증거를 검토하세요.
모델 · 공급자를 구성하고 연결 테스트를 실행한 뒤 사용 가능한지 확인하세요.
데이터 세트 · 소스와 선택적 입력 및 참조 필드를 선언하세요.
데이터 세트를 다운로드하고 상태가 준비될 때까지 기다리세요.
작업 공간 · 사용자 템플릿을 작성하세요. 레코드 필드는 {{ placeholders }}를 통해 렌더링됩니다.
블라인드 쌍대 판정을 실행하고 사람 검토를 저장한 다음 보고서를 생성하세요.
엔드포인트가 저장되었습니다. 실행을 시작하기 전에 연결을 테스트하세요.
기능 프로브가 완료되었습니다. 선언된 기능 설정은 변경되지 않았습니다.
사용자 기능 선언이 감지 증거와 함께 저장되었습니다.
사전 점검 준비됨: {{samples}}개 샘플, {{requests}}개 요청, 예상 {{tokens}}개 토큰, {{cost}}.
사전 점검 차단됨: {{issues}}
{{benchmark}}이(가) 변경 불가능한 구성 스냅샷과 함께 대기열에 추가되었습니다.
실행이 새 변경 불가능한 구성 스냅샷으로 복제되었습니다.
벤치마크 재실행이 원본 실행 링크와 함께 대기열에 추가되었습니다.
실패한 샘플이 새 시도로 대기열에 추가되었습니다.
실행이 보관되었습니다. 증거는 삭제될 때까지 API를 통해 계속 사용할 수 있습니다.
향후 작업 요청을 위한 실행 동시성 상한이 업데이트되었으며 평가 스냅샷은 변경되지 않습니다.
{{benchmark}}은(는) 이제 {{status}}입니다.
{{format}} {{reportType}} 보고서가 생성되었습니다.
읽기 전용 공유 링크({{expires}} 만료): {{url}}
버전 관리된 프롬프트 패키지가 저장되었습니다.
데이터 세트 버전이 등록되었습니다.
사용자가 생성되었습니다. 지금 이 API 토큰을 복사하세요: {{token}}
버전 관리된 평가 스위트가 저장되었습니다.
{{count}}개 스위트 실행이 대기열에 추가되었습니다.
검증된 미디어 자산이 업로드되어 사용자 지정 실행에 선택되었습니다.
먼저 사용 가능한 엔드포인트를 선택하고 미디어 자산을 업로드하거나 선택하세요.
사용자 지정 멀티모달 실행이 변경 불가능한 자산 스냅샷과 함께 대기열에 추가되었습니다.
라이선스가 수락되었습니다. 이제 데이터 세트를 다운로드할 수 있습니다.
데이터 세트가 다운로드, 검증 및 캐시되었습니다.
데이터 세트 업로드 체크섬이 검증되어 로컬 데이터 세트 캐시에 저장되었습니다.
데이터 세트 캐시 체크섬과 크기가 검증되었습니다.
데이터 세트 캐시가 제거되었습니다. 다시 다운로드하거나 업로드할 수 있습니다.
같은 벤치마크 버전에서 서로 다른 두 실행을 선택하세요.
사람 검토가 자동화된 결과와 별도로 저장되었습니다.
블라인드 쌍대 판정 증거와 교환 테스트 결과가 저장되었습니다.
독립 LLM 판정 평가가 근거 증거와 함께 저장되었습니다.
작업 우선순위가 {{priority}}(으)로 업데이트되었습니다.`.split("\n"),
  ms: `Badan permintaan lalai (JSON)
Pakej gesaan untuk larian baharu
Gantian badan permintaan larian (JSON)
Ujian sambungan dan pelaksanaan menggunakan titik akhir tersimpan. Gantian larian digabungkan selepas lalai set dan penanda aras; medan yang dipaksa oleh penanda aras masih diutamakan. Kekunci API tidak pernah dikembalikan kepada pelayar.
Bukti pengesanan dan pengisytiharan pengguna kekal berasingan.
Tambah titik akhir model sebelum menyiasat keupayaan.
Belum ada hasil siasatan dimuatkan.
Cipta set daripada katalog ruang kerja.
Contoh few-shot (tatasusunan JSON)
Gunakan tindakan muat naik set data untuk fail tempatan.
Medan input
Medan rujukan (output)
Semakan pantas multimodal tersuai
Muat naik aset dahulu.
Fail disahkan melalui tandatangan MIME, dialamatkan mengikut kandungan dan disimpan di luar memori pelayar sebelum memasuki petikan larian.
Pilih imej, audio, video atau PDF
Memuat naik dan mengesahkan aset…
Badan permintaan lalai set (JSON)
Belum ada set dicipta.
Daftarkan versi set data untuk mengurus muat turun dan lesen.
Sahkan keserasian dan anggarkan kerja tanpa mencipta entri baris.
Sahkan titik akhir model untuk mencipta larian pertama.
Tetapkan had
Laksanakan
Jalankan semula penanda aras
Tiada kerja dalam baris.
Kemas kini langsung distrim daripada saluran acara pekerja.
Tiada pajakan pekerja aktif.
Keadaan
Tamat tempoh pajakan
Induk
Perbandingan model dan larian
Larian mesti menggunakan versi penanda aras yang sama. Perbezaan ialah larian A tolak larian B.
Larian B
Laporan
Jana laporan mudah alih untuk
, atau muat turun artifak terdahulu.
Lengkap untuk satu model
Perbandingan berbilang model
Regresi
Kebolehpercayaan
Jana HTML
Jana Markdown
Jana CSV
Jana Parquet
Pilih larian dalam halaman Larian sebelum menjana laporan.
Skor penyemak kekal berasingan daripada bukti deterministik dan bukti hakim.
Pilih larian dan sampel daripada halaman Larian untuk menyemaknya.
Peranan
Pemerhati
Penilai
Pentadbir
Cipta pengguna token API
Pengguna dan jejak audit
Pentadbiran pengguna memerlukan token pembawa pentadbir apabila pengesahan pelayan didayakan.
Acara audit terkini
Entiti
Bila
Tetapan masa jalan dikonfigurasi melalui persekitaran penggunaan; nilai sensitif tidak pernah dikembalikan kepada pelayar.
Versi skema
Token pembawa pentadbir atau pengguna
Simpan token
Kosongkan token
Panduan operasi SQLite
SQLite sesuai untuk kegunaan setempat atau pasukan kecil. Gunakan PostgreSQL atau MongoDB bagi penggunaan pekerja berbilang proses dan teragih; konfigurasikan had pekerja global dengan tetapan persekitaran penggunaan.
Tukar kepada
mod
Diambil hanya selepas sampel ini dipilih.
Larian ini belum mempunyai percubaan tersimpan.
Anomali
Tiada sampel sepadan dengan penapis ini.
Dikemas kini dengan acara larian langsung
Tiada acara kitar hayat tugas atau sampel direkodkan.
Belum ada bukti keupayaan yang diberi skor.
Tiada anomali atau regresi penting dikesan.
Muatkan halaman bukti seterusnya
Peringkat semakan
Semakan utama
Semakan kedua
Pengadjudikasian
Rubrik (JSON)
Label (dipisahkan dengan koma)
Ini merekodkan keputusan muktamad untuk semua semakan utama dan kedua yang disimpan.
Persetujuan semakan
Buka sampel untuk memuatkan persetujuan semakan.
Semakan tersimpan
Tiada semakan manusia disimpan untuk percubaan ini.
LLM sebagai hakim
Titik akhir hakim bebas
Minta penilaian hakim
Tiada penilaian hakim bebas direkodkan.
Artifak laporan
Hakim berpasangan buta
Identiti model tidak pernah dihantar kepada hakim.
Bandingkan dengan percubaan sampel sepadan
Penilaian hakim jawapan tunggal
Atau tampal ID percubaan sampel
Jalankan ujian pertukaran susunan terbalik
Jalankan perbandingan buta
Persetujuan hakim
Buka sampel untuk memuatkan persetujuan hakim.
Peta haba analisis
Setiap sel menyimpan bilangan sampel, selang keyakinan 95%, kependaman, kos dan delta garis asas pilihan.
Carta keupayaan interaktif
Klik atau gunakan Enter pada bar untuk memeriksa hasil keupayaan model.
Selesaikan larian untuk mengisi bar skor interaktif.
Selesaikan larian untuk mengisi analisis ini.
Sampel / SK 95%
Hanya A betul
Hanya B betul
Metrik
Kadar kejayaan
Kependaman P95
Model tempatan saya
Pilihan untuk perkhidmatan Ollama tempatan
Gunakan kapasiti titik akhir
sampel, ramalan, ralat
Tidak dapat mencapai perkhidmatan penilaian.
Siasatan keupayaan menghantar permintaan kecil kepada pembekal ini dan mungkin dikenakan caj API. Teruskan?
Buang data cache untuk {{dataset}} v{{version}}? Versi berdaftar akan kekal.
7 langkah
Daftarkan titik akhir model dan set data, kemudian letakkan larian penilaian dalam baris dan periksa bukti.
Model · konfigurasikan pembekal, jalankan ujian sambungan dan sahkan ia tersedia.
Set data · isytiharkan sumber serta, secara pilihan, medan input dan rujukan.
Muat turun set data dan tunggu sehingga statusnya sedia.
Ruang kerja · tulis templat pengguna; medan rekod dirender melalui {{ placeholders }}.
Jalankan pengadilan berpasangan buta, simpan semakan manusia dan jana laporan.
Titik akhir disimpan. Uji sambungannya sebelum memulakan larian.
Siasatan keupayaan selesai. Tetapan keupayaan yang diisytiharkan tidak diubah.
Pengisytiharan keupayaan pengguna disimpan bersama bukti pengesanan.
Prasemak sedia: {{samples}} sampel, {{requests}} permintaan, {{tokens}} token dianggarkan, {{cost}}.
Prasemak disekat: {{issues}}
{{benchmark}} diletakkan dalam baris dengan petikan konfigurasi tidak berubah.
Larian diklon dengan petikan konfigurasi tidak berubah yang baharu.
Larian semula penanda aras diletakkan dalam baris dengan pautan kepada larian sumbernya.
Sampel gagal diletakkan dalam baris sebagai percubaan baharu.
Larian diarkibkan. Buktinya kekal tersedia melalui API sehingga dipadamkan.
Had keserentakan larian dikemas kini untuk tuntutan tugas masa depan; petikan penilaiannya kekal tidak berubah.
{{benchmark}} kini {{status}}.
Laporan {{reportType}} {{format}} dijana.
Pautan kongsi baca sahaja (tamat {{expires}}): {{url}}
Pakej gesaan berversi disimpan.
Versi set data didaftarkan.
Pengguna dicipta. Salin token API ini sekarang: {{token}}
Set penilaian berversi disimpan.
{{count}} larian set diletakkan dalam baris.
Aset media yang disahkan dimuat naik dan dipilih untuk larian tersuai.
Pilih titik akhir tersedia dan muat naik atau pilih aset media dahulu.
Larian multimodal tersuai diletakkan dalam baris dengan petikan aset tidak berubah.
Lesen diterima. Set data kini boleh dimuat turun.
Set data dimuat turun, disahkan dan dicache.
Jumlah semak muat naik set data disahkan dan disimpan dalam cache set data tempatan.
Jumlah semak dan saiz cache set data disahkan.
Cache set data dibuang. Anda boleh memuat turun atau memuat naiknya lagi.
Pilih dua larian berlainan daripada versi penanda aras yang sama.
Semakan manusia disimpan berasingan daripada keputusan automatik.
Bukti hakim berpasangan buta dan hasil ujian pertukaran disimpan.
Penilaian LLM-sebagai-hakim bebas disimpan bersama bukti alasan.
Keutamaan tugas dikemas kini kepada {{priority}}.`.split("\n"),
};

// Only literals authored by the client are eligible for word-level fallback.
// This is deliberately an allow-list: endpoint names, benchmark names, raw
// responses, and provider errors must remain exactly as the server supplied.
export const staticSourceTexts = new Set([
  "Add model endpoint", "Display name", "Base URL", "Model name", "Protocol profile", "API key", "Custom headers (JSON)", "Default request body (JSON)", "Endpoint concurrency", "Shared API-key concurrency", "Requests / minute", "Tokens / minute", "Requests / second", "Input tokens / minute", "Output tokens / minute", "Input / 1M tokens", "Output / 1M tokens", "Currency", "Tags (comma-separated)", "Notes", "Saving...", "Save encrypted endpoint",
  "Run configuration", "Benchmark pack", "Prompt package for a new run", "Built-in benchmark prompt", "Run Request Body override (JSON)", "Run concurrency cap", "Connection tests and execution use the saved endpoint. The run override is merged after suite and benchmark defaults; benchmark-forced fields still win. API keys never return to the browser.", "Models", "No model endpoints yet.", "Test connection", "Probe capabilities", "Queue selected benchmark", "User: unknown", "User: supported", "User: unsupported",
  "Model capabilities", "Detection evidence and user declarations remain separate.", "Add a model endpoint before probing capabilities.", "No probe result loaded yet.", "Benchmarks", "Benchmark", "Version", "Source", "Status", "Modalities", "Operation", "Enable", "Disable", "Managed by pack",
  "Evaluation suites", "Create a suite from the Workspace catalog.", "Queue on", "Create prompt package", "Name", "Prompt type", "Official prompt", "Platform default", "User custom", "Benchmark variant", "Language-specific", "System message", "User template", "Few-shot examples (JSON array)", "Output format (JSON)", "Response parser (JSON)", "Scoring rule (JSON)", "Change log", "Save versioned prompt",
  "Register dataset version", "Dataset ID", "Revision", "Source HTTPS URL", "Use the dataset upload action for local files.", "Expected SHA-256 checksum", "Credential binding ID", "License text", "Input field", "Reference (output) field", "Register dataset", "Preview", "Edit", "Delete", "Save changes", "Cancel", "Data preview", "Delete dataset version?", "Custom multimodal quick check", "Endpoint", "Select available endpoint", "Sample ID", "Prompt", "Expected text answer", "Uploaded media", "Upload an asset first", "Queue multimodal run", "Media asset upload", "Files are validated by MIME signature, content-addressed, and stored outside browser memory before they enter a run snapshot.", "Choose image, audio, video, or PDF", "Uploading and validating asset...",
  "Create evaluation suite", "Benchmarks (id@version)", "Suite default Request Body (JSON)", "Prompt overrides (JSON)", "Weight configuration (JSON)", "Description", "Save suite", "No suites have been created.", "Benchmark registry", "Dataset cache", "Register a dataset version to manage downloads and licenses.", "No source URL", "Accept license", "Download and verify",
  "Run preflight", "Validate compatibility and estimate work without creating a queue entry.", "Checking…", "Preflight", "Evaluation runs", "Verify a model endpoint to create the first run.", "Inspect", "Run cap", "Set cap", "Execute", "Pause", "Resume", "Clone", "Rerun benchmark", "Retry failed", "Archive", "Cancel",
  "Task queue", "No queued work exists.", "Workers", "Live updates are streamed from the worker event channel.", "No worker leases are active.", "Worker", "Task", "Run", "State", "Lease expiry", "Parent", "Priority", "Attempts", "Created",
  "Model and run comparison", "Runs must use the same benchmark version. Differences are run A minus run B.", "Run A", "Run B", "Select completed run", "Compare", "Reports", "Generate a portable report for", ", or download previous artifacts.", "Report type", "Single-model complete", "Multi-model comparison", "Regression", "Prompt comparison", "Reliability", "Cost", "Human review", "Related completed run", "Select run", "Generate HTML", "Generate Markdown", "Generate PDF", "Generate JSON", "Generate CSV", "Generate Parquet", "Choose a run in the Runs page before generating a report.",
  "Reviewer scores remain separate from deterministic and judge evidence.", "Select a run and sample from the Runs page to review it.", "Create user", "Email", "Role", "Viewer", "Reviewer", "Evaluator", "Admin", "User concurrency cap", "Create API-token user", "Users and audit trail", "User administration needs an administrator bearer token when server authentication is enabled.", "Recent audit events", "Action", "Entity", "When",
  "System settings", "Runtime settings are configured through the deployment environment; sensitive values never return to the browser.", "Database", "Schema version", "Health", "Queue", "Disk", "Theme", "Workspace language", "Administrator or user bearer token", "Save token", "Clear token", "SQLite operating guidance", "SQLite is suitable for local or small-team use. Use PostgreSQL or MongoDB for multi-process, distributed worker deployments; configure global worker ceilings with deployment environment settings.", "Switch to", "mode",
  "Media preview", "Fetched only after this sample is selected.", "Loading", "evidence…", "Audio preview unavailable.", "Video preview unavailable.", "Download attached file", "Sample evidence", "This run has no saved attempts yet.", "Search samples", "All states", "Succeeded", "Failed", "Pending", "Running", "Correctness", "Correct", "Incorrect", "Capability", "Modality", "Language", "Difficulty", "Error type", "Any error", "API error", "Parser error", "Judge", "Disagreement", "No disagreement", "Anomaly", "None", "No samples match these filters.", "Human review", "Load next 100 samples",
  "Run executive summary", "Completion", "Accuracy", "Latency", "Loading summary...", "Durable run log", "Refreshes with live run events", "No task or sample lifecycle events have been recorded.", "Capability evidence", "No scored capability evidence yet.", "Score", "Samples", "Run signals", "No significant anomalies or regressions detected.", "Loading next page…", "Load next evidence page", "Reviewer ID", "Review stage", "Primary review", "Secondary review", "Adjudication", "Rubric (JSON)", "Labels (comma-separated)", "This records a final decision over all saved primary and secondary reviews.", "Save review", "Review agreement", "Open a sample to load review agreement.", "Saved reviews", "No human review has been saved for this attempt.", "LLM-as-judge", "Independent judge endpoint", "Request judge assessment", "Judge evidence", "No independent judge assessment has been recorded.", "Report artifacts",
  "Blinded pairwise judge", "Model identities are never sent to the judge.", "Compare with matching sample attempt", "Single-answer judge assessment", "Or paste a sample attempt ID", "Run reverse-order swap test", "Run blinded comparison", "Judge agreement", "Open a sample to load judge agreement.", "Analysis heatmaps", "Every cell keeps its sample count, 95% confidence interval, latency, cost, and optional baseline delta.", "Baseline run", "No baseline", "Interactive capability chart", "Click or use Enter on a bar to inspect a model-capability result.", "Complete a run to populate interactive score bars.", "Complete runs to populate this analysis.", "Row", "Column", "Samples / 95% CI", "Baseline / Δ", "Errors", "A-only correct", "B-only correct", "Latency difference", "Cost difference", "Metric", "Success rate", "P95 latency", "Output tokens",
  "My local model", "Optional for a local Ollama service", "Stored encrypted", "Unlimited", "Use endpoint capacity", "production, vision", "sample, prediction, error", "Unable to reach the evaluation service.",
  "configured", "cost not configured", "executed", "paused", "resumed", "cancelled", "single model", "multi model", "prompt comparison", "Capability probing sends small requests to this provider and may incur API charges. Continue?", "Remove the cached data for {{dataset}} v{{version}}? The registered version will remain.",
  "Overview", "Configure", "Catalog", "Operations", "Insights", "Reporting", "Quality review", "Administration", "Evaluation workflow", "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist.", "Runs", "Datasets", "Analysis", "Open Models", "Open Datasets", "Review Datasets", "Open Runs", "Inspect Runs", "Open Analysis", "6 steps", "Selected model endpoint", "Select a configured endpoint to inspect it.", "Register a source, then prepare, validate, and inspect it here.", "Select a run from Run inventory to open its summary, evidence, and lifecycle history.", "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.",
  "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.", "Endpoint inventory", "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.", "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.", "Inspect detected capability evidence separately from the declarations used by run compatibility checks.", "No endpoints available", "Choose an endpoint to inspect its detection and declaration evidence.",
  "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.", "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.", "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.", "No dataset versions", "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.", "Dataset inventory", "Select a source version to inspect its cache, metadata, and lifecycle actions.", "Open suite builder", "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.", "No evaluation suites", "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.", "Suite inventory", "Choose a versioned suite to inspect composition and queue it on an available endpoint.",
  "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.", "4 workbench modes", "Run inventory", "Select a snapshot to inspect lifecycle evidence and exportable artifacts.", "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.", "Queue dataset evaluation", "Choose an available dataset, prompt version, and endpoint for a new evaluation.", "Selected run inspector", "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.", "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.", "Queue inventory", "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.", "Find task", "Task status", "No tasks match the current filters.", "Track active task leases and the worker capacity currently consuming evaluation work.", "No active worker leases", "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.", "Open task queue", "Active leases", "Connected workers", "Tasks currently leased or running", "Distinct workers with an active lease", "Pending tasks reported by system health", "Health signal unavailable", "Active worker leases", "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.",
  "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.", "Loading analysis", "Analysis matrix", "The analysis matrix is loading from the evaluation service.", "Analysis context", "The selected baseline applies to every evidence cell and delta shown below.", "Interactive capability chart", "Click or use Enter on a bar to inspect the supplied model-capability result.", "Compare runs", "Compare two completed runs from the same benchmark version and retain the complete evidence trail.", "Comparison sources", "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.", "Comparison evidence", "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.", "Choose two completed runs to begin an evidence-backed comparison.",
  "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.", "Report context", "Select the run whose immutable evidence snapshot should anchor this report.", "Report source run", "Select a report source", "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.", "Select a run to generate a portable report or inspect saved artifacts.", "Generate report", "Select the report shape, then generate the download format needed by the next review or handoff.", "Report artifacts", "Download a generated artifact or create a scoped share link with explicit evidence and download controls.", "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.", "Select an evidence sample", "Review context", "Choose the evaluation snapshot and sample before opening human or independent judge workflows.", "Review run", "Review sample", "Select a run to begin a human or judge review.", "Human review workflow", "Provision constrained API users and keep recent administrative activity alongside the current inventory.", "User inventory", "Create a token-bearing account with the least-privileged role and an optional concurrency ceiling.", "Roles, rate ceilings, and status remain visible before issuing additional credentials.", "The latest recorded administrative changes are retained as an audit trail, separate from user-authored values.", "Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls.", "Application and storage", "Access and preferences", "The token remains only in this browser session. Clear it when you no longer need protected access.", "Operating guidance", "Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only.",
  "How to use this workspace", "7 steps", "Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence.", "1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available.", "2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields.", "3. Download and verify", "Download the dataset and wait until its status is ready.", "4. Create a prompt package", "Workspace · write the user template; record fields render through {{ placeholders }}.", "4. Queue a dataset run", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.", "5. Inspect evidence", "Runs · open the run to review samples, scores, latency, cost, and errors.", "6. Analyze results", "Analysis · inspect evaluation dimensions or compare two completed runs.", "7. Judge, review, and report", "Run blind pairwise judging, save human reviews, and generate reports.",
  "Filter benchmarks", "Name, source, status…", "Find run", "Benchmark, status, or ID", "Run status", "No runs match the current filters.", "Pause download", "Validate cache", "Clear cache", "Retry download", "Upload local revision", "Benchmark composition", "Queue suite", "Uses each selected endpoint’s saved connection and capacity configuration.", "No available endpoints are ready to receive this suite.", "Loading disk usage…", "No events available.", "Comparing…", "registered versions", "total runs", "tasks visible",
  "Endpoint saved. Test its connection before starting a run.", "Capability probe completed. Declared capability settings were not changed.", "User capability declaration saved alongside detection evidence.", "Preflight ready: {{samples}} samples, {{requests}} requests, {{tokens}} estimated tokens, {{cost}}.", "Preflight blocked: {{issues}}", "{{benchmark}} queued with an immutable configuration snapshot.", "Run cloned with a new immutable configuration snapshot.", "Benchmark rerun queued with a link to its source run.", "Failed samples were queued as new attempts.", "Run archived. Its evidence remains available through the API until deleted.", "Run {{action}}.", "Run concurrency ceiling updated for future task claims; its evaluation snapshot remains unchanged.", "{{benchmark}} is now {{status}}.", "{{dataset}} download paused.", "{{format}} {{reportType}} report generated.", "Read-only share link (expires {{expires}}): {{url}}",   "Versioned prompt package saved.", "Dataset version registered.", "Dataset version updated.", "Dataset version deleted.", "Preview unavailable.", "User created. Copy this API token now: {{token}}", "Versioned evaluation suite saved.", "{{count}} suite run(s) queued.", "Validated media asset uploaded and selected for the custom run.", "Select an available endpoint and upload or select a media asset first.", "Custom multimodal run queued with an immutable asset snapshot.", "License accepted. The dataset can now be downloaded.", "Dataset downloaded, verified, and cached.", "Dataset upload checksum verified and stored in the local dataset cache.", "Dataset cache checksum and size were verified.", "Dataset cache removed. You can download or upload it again.", "Choose two different runs from the same benchmark version.", "Human review saved separately from automated results.", "Blinded pairwise judge evidence and swap-test results saved.", "Independent LLM-as-judge assessment saved with rationale evidence.", "Task priority updated to {{priority}}.",
]);

const handAuthoredStaticPhraseSources = [...staticSourceTexts].filter((source) =>
  localeIds.slice(1).every((locale) => !protocolProfilePhrases[locale][source] && !phrases[locale][source]),
);

for (const locale of localeIds.slice(1)) {
  const translations = handAuthoredStaticPhraseTranslations[locale];
  if (!translations || translations.length !== handAuthoredStaticPhraseSources.length) {
    throw new Error(`Static phrase catalog is incomplete for ${locale}.`);
  }
  Object.assign(phrases[locale], Object.fromEntries(handAuthoredStaticPhraseSources.map((source, index) => [source, translations[index]!])));
}

phrases.ja["My local model"] = "ローカル モデル";

export function translateStaticText(locale: Locale, text: string): string {
  if (locale === "en") return text;
  const match = /^(\s*)(.*?)(\s*)$/.exec(text);
  const prefix = match?.[1] ?? "";
  const source = match?.[2] ?? text;
  const suffix = match?.[3] ?? "";
  const exact = protocolProfilePhrases[locale][source] ?? phrases[locale][source];
  if (!staticSourceTexts.has(source) && !exact) return text;
  if (exact) return `${prefix}${exact}${suffix}`;
  const wordIndex = localeIds.indexOf(locale) - 1;
  return `${prefix}${source.replace(/\{\{[A-Za-z]+\}\}|[A-Za-z]+(?:-[A-Za-z]+)*/g, (token) => token.startsWith("{{") ? token : words[token.toLowerCase()]?.[wordIndex] ?? token)}${suffix}`;
}

export function hasExplicitStaticTranslation(locale: Locale, text: string): boolean {
  if (locale === "en") return true;
  const source = /^\s*(.*?)\s*$/.exec(text)?.[1] ?? text;
  return Boolean(protocolProfilePhrases[locale][source] ?? phrases[locale][source]);
}

export function translateStaticTemplate(locale: Locale, template: string, values: Record<string, string | number> = {}): string {
  return translateStaticText(locale, template).replace(/\{\{([A-Za-z]+)\}\}/g, (_match, key: string) => String(values[key] ?? ""));
}
