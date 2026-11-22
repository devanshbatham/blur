"""Multilingual circuits: Chinese, Japanese, Korean, Russian, French, Spanish, Dutch, Portuguese.

Everything here is weights: patterns over UTF-8 bytes, compiled by the same DSL as the rest of the network. A Han,
kana or Hangul character is three bytes (a lead byte and two continuation bytes), a Cyrillic or accented Latin letter
two; the byte classes below follow that structure. No checksums (the network cannot afford the arithmetic): identifier
formats are matched by shape and, where a shape is not specific enough, only after a key or cue.

Rules (all general statements about how these languages write personal data):
  1. a value after a field key in any of the eight languages ("姓名：", "電話番号：", "주소:", "Пароль:", "Adresse :",
     "Teléfono:", "Wachtwoord:", "Morada:") is that kind of value;
  2. a person is marked by honorifics and titles (先生/女士/様/さん/씨/님, г-н, M./Mme, Sr./Sra., dhr./mevr.), by a
     patronymic or initials (Russian), by a role word before the name (收货人, 配偶), by a greeting or a sign-off;
  3. dates in East Asian and Russian formats and with Dutch / Romance month names;
  4. national phone formats that are specific enough to need no cue (public hotlines excluded);
  5. national identifier formats (resident IDs, CPF, DNI/NIE, СНИЛС, CURP/RFC, licence plates);
  6. street addresses in national formats;
  7. credentials and codes stated in a sentence ("验证码是482915", "パスワードは…", "비밀번호는…", "пароль: …").
"""
from ..dsl import byteset
from ..patterns import parse_var


def L(s: str) -> str:
    """A literal in byte view (UTF-8 bytes as latin-1 chars), with the pattern's special characters escaped."""
    b = s.encode("utf-8").decode("latin-1")
    return "".join("\\" + ch if ch in "[](){}?+*\\|" else ch for ch in b)


def G(*words: str) -> str:
    """A group of literal words (an alternation) in byte view."""
    return "(" + "|".join(w.encode("utf-8").decode("latin-1") for w in words) + ")"


# byte classes (written in byte view: each char below is one byte value)
CONT = "\x80-\xbf"
HANB = "[\xe3-\xe9" + CONT + "]"          # bytes of Han / kana characters (lead E3-E9, continuation 80-BF)
HANGB = "[\xea-\xed" + CONT + "]"         # bytes of Hangul syllables
CYRB = "[\xd0\xd1" + CONT + "]"           # bytes of Cyrillic letters
LATB = "[A-Za-z\xc3" + CONT + "'\\-]"      # Latin letters incl. accented ones (C3 xx) and apostrophe / hyphen
DIG = "[0-9]"

ZH_SURNAMES = ("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤欧阎庞樊兰殷施翟倪洪柳单温季骆华耿关柴"
               "葛祝邢安易乔左鲁焦裴申花牛童甘纪芦岳凌商路宁滕蓝伍费卜柏薄邬鞠游俞仇凤苗詹庄祁丘")
ZH_COMPOUND = ("欧阳", "司马", "诸葛", "上官", "东方", "慕容", "令狐", "皇甫", "尉迟", "公孙", "夏侯", "司徒", "端木", "长孙")
KO_SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용봉"
KO_NOT_NAME = ("고객", "여러분", "회원", "선생", "부모", "학부모", "담당자", "기사", "사장", "손님", "환자", "보호자", "직원", "관리자", "운영자", "상담원",
               "매니저", "선배", "후배", "형님", "누님", "언니", "오빠", "이모", "삼촌", "고모", "가족", "이웃", "친구", "동료", "교수", "원장", "이사")
RU_GIVEN = ("Александр Алексей Андрей Анна Анастасия Антон Артём Артем Борис Вадим Валентина Валерий Василий Вера Виктор Виктория Владимир Владислав "
            "Галина Георгий Григорий Дарья Денис Дмитрий Евгений Евгения Екатерина Елена Елизавета Иван Игорь Илья Ирина Кирилл Константин Ксения Лариса "
            "Леонид Лилия Любовь Людмила Максим Маргарита Марина Мария Михаил Надежда Наталья Наталия Никита Николай Нина Оксана Олег Ольга Павел Пётр Петр "
            "Полина Роман Руслан Светлана Сергей Софья София Станислав Степан Тамара Татьяна Тимур Фёдор Федор Юлия Юрий Яна Ярослав Катя Маша Саша Серёжа "
            "Сережа Дима Коля Миша Таня Лена Оля Наташа Света Женя Паша Вова Ваня Петя Настя Даша Юля Аня Рустам Альберт Ринат Айгуль Гульнара Камила Эльвира "
            "Зарина Тимофей Ангелина Алина Вероника Кристина Карина Арина Ульяна Василиса Глеб Егор Матвей Захар Лев Арсений Даниил Фатима Эдуард Геннадий "
            "Аркадий Семён Семен Вячеслав Анатолий Филипп Ильдар Айдар Динара Регина Варвара Лидия Зоя").split()

KEYS = {
    "GIVENNAME": ("姓名", "名字", "收货人", "收件人", "联系人", "紧急联系人", "负责人", "经办人", "申请人", "借款人", "持卡人", "户名", "患者姓名", "学生姓名",
                  "氏名", "お名前", "受取人", "担当者", "担当医", "責任者", "管理者", "申請者", "保護者", "契約者",
                  "이름", "성명", "성함", "담당자", "수령인", "보호자", "환자명", "고객명", "예금주", "신청인",
                  "ФИО", "Имя", "Фамилия", "Получатель", "Отправитель", "Пациент", "Клиент", "Ответственный", "Заявитель", "Владелец",
                  "Nom", "Prénom", "Nom complet", "Destinataire", "Titulaire", "Nombre", "Nombre completo", "Apellidos", "Apellido", "Paciente",
                  "Destinatario", "Remitente", "Naam", "Voornaam", "Achternaam", "Ontvanger", "Rekeninghouder", "Nome", "Nome completo", "Apelido",
                  "Sobrenome", "Destinatário", "Responsável"),
    "TEL": ("电话", "手机", "手机号", "手机号码", "联系电话", "联系方式", "座机", "電話", "電話番号", "携帯", "携帯電話", "連絡先", "전화", "전화번호", "휴대폰",
            "휴대전화", "연락처", "핸드폰", "Телефон", "Мобильный телефон", "Мобильный", "Контактный телефон", "Тел.", "Téléphone", "Tél.", "Portable",
            "Teléfono", "Celular", "Cel.", "Móvil", "Telefoon", "Mobiel", "Telefone", "Telemóvel", "Contacto", "WhatsApp"),
    "ADDRESS": ("地址", "住址", "家庭住址", "收货地址", "收件地址", "现住址", "居住地址", "通讯地址", "住所", "ご住所", "現住所", "お届け先", "届け先", "送付先",
                "주소", "배송지", "거주지", "Адрес", "Адрес доставки", "Адрес регистрации", "Место жительства", "Adresse", "Adresse de livraison",
                "Adresse de facturation", "Dirección", "Dirección de residencia", "Domicilio", "Adres", "Woonadres", "Bezorgadres", "Endereço", "Morada"),
    "BOD": ("出生日期", "生日", "生年月日", "誕生日", "생년월일", "생일", "Дата рождения", "Date de naissance", "Fecha de nacimiento", "Geboortedatum",
            "Data de nascimento"),
    "ID": ("身份证号", "身份证号码", "身份证", "证件号码", "证件号", "工号", "学号", "学籍号", "会员号", "会员卡号", "客户号", "客户编号", "病历号", "就诊卡号",
           "护照号码", "护照号", "驾驶证号", "车牌号", "マイナンバー", "個人番号", "社員番号", "会員番号", "患者番号", "診察券番号", "免許証番号", "旅券番号",
           "パスポート番号", "保険証番号", "주민등록번호", "외국인등록번호", "사번", "학번", "회원번호", "고객번호", "여권번호", "운전면허번호", "차량번호",
           "Паспорт", "Серия и номер паспорта", "СНИЛС", "ИНН", "Полис ОМС", "Полис", "Табельный номер", "N° de sécurité sociale",
           "Numéro de sécurité sociale", "NIR", "Matricule", "N° client", "Numéro client", "N° adhérent", "IPP", "N° de dossier", "DNI", "NIE", "NIF",
           "CURP", "RFC", "Cédula", "Número de cliente", "Matrícula", "Placa", "BSN", "Burgerservicenummer", "Klantnummer", "Personeelsnummer",
           "Paspoortnummer", "Rijbewijsnummer", "Kenteken", "Polisnummer", "Lidnummer", "CPF", "RG", "Cartão de Cidadão", "N.º de utente",
           "N.º de sócio", "N.º de cliente", "Número de contribuinte", "NISS"),
    "SECRET": ("密码", "口令", "登录密码", "初始密码", "支付密码", "验证码", "校验码", "动态码", "取件码", "提货码", "WiFi密码", "wifi密码", "パスワード",
               "暗証番号", "認証コード", "確認コード", "비밀번호", "인증번호", "비번", "Пароль", "Код подтверждения", "Код доступа", "Код домофона", "ПИН",
               "Mot de passe", "Code d'accès", "Code PIN", "Digicode", "Contraseña", "Clave", "Código de verificación", "Código de acceso",
               "Wachtwoord", "Pincode", "Toegangscode", "Senha", "Código de acesso", "Código de verificação"),
    "USERNAME": ("用户名", "账号", "帐号", "登录账号", "微信号", "微信", "QQ号", "ユーザー名", "ユーザーID", "ログインID", "LINE ID", "아이디", "카카오톡 ID",
                 "Логин", "Имя пользователя", "Identifiant", "Nom d'utilisateur", "Usuario", "Nombre de usuario", "Gebruikersnaam", "Utilizador",
                 "Usuário", "Nome de utilizador"),
    "CARD": ("银行卡号", "银行卡", "卡号", "账户", "还款账户", "收款账户", "口座番号", "振込先", "계좌번호", "계좌", "Номер счёта", "Номер счета",
             "Расчётный счёт", "Номер карты", "IBAN", "RIB", "N° de compte", "Numéro de compte", "Cuenta", "CLABE", "Rekeningnummer", "Conta",
             "Chave Pix", "支付宝账号", "支付宝"),
}
SEPS = (":", "：", "=", "是", "为", "は", " :", ": ", "： ", " : ", "= ", "은 ", "는 ", "은", "는")


def multilingual(c):
    n = c.n
    # name claims are checked later by the name guard in context_net (the English word list is built after this module)
    _add = c.add
    c._frame_names = getattr(c, "_frame_names", [])
    def add(label, sig, tier=0):
        if label in ("GIVENNAME", "LASTNAME"):
            c._frame_names.append((label, sig, tier))
        else:
            _add(label, sig, tier)
    c.add = add
    try:
        _multilingual(c)
    finally:
        c.add = _add


def _multilingual(c):
    n = c.n
    cls = lambda chars: n.cls(chars)
    allb = "".join(chr(i) for i in range(1, 256))
    nonl = cls(allb.replace("\n", ""))
    sp = cls(" \t")
    cont = cls("".join(chr(i) for i in range(0x80, 0xC0)))
    han_lead = cls("".join(chr(i) for i in range(0xE4, 0xEA)))
    kana_lead = cls("\xe3")
    hang_lead = cls("".join(chr(i) for i in range(0xEA, 0xEE)))
    cjk_char = n.AND(n.OR(han_lead, kana_lead, hang_lead, force=True), cont.at(1), cont.at(2))   # first byte of a 3-byte char
    han_char = n.AND(han_lead, cont.at(1), cont.at(2))
    hang_char = n.AND(hang_lead, cont.at(1), cont.at(2))
    hanb, hangb, cyrb, latb = (cls(parse_var(x)[0][0]) for x in (HANB, HANGB, CYRB, LATB))
    digit = cls("0123456789")

    def P(pattern, pre=None, post=None, **kw):
        # pre / post are character-class bodies with ranges ("A-Za-z0-9"), expanded like a [...] class
        cs = lambda x: parse_var("[" + x + "]")[0][0] if x else None
        return n.match(parse_var(pattern), cs(pre), cs(post), **kw)

    def lits(words):
        return n.OR(*[n.lit(w.encode("utf-8").decode("latin-1")) for w in words], force=True)

    # ---------- 1. values after field keys ----------
    sep_end = None
    for label, keys in KEYS.items():
        key_span, key_end = P(G(*keys), pre="A-Za-z")
        # the separator after the key; the value starts on the next byte
        after = []
        for s in SEPS:
            b = s.encode("utf-8").decode("latin-1")
            after.append(n.AND(key_end.at(-len(b)), n.lit(b).at(-(len(b) - 1))))
        vstart_at = n.OR(*after, force=True)            # fires on the last byte of the separator
        if label == "TEL":
            body = cls("0123456789 ()+-.")
            start = n.AND(cls("0123456789+("), vstart_at.at(-1))
            val = n.prop_right(start, body, 5)
            val = n.AND(val, n.fill(val, n.run(digit, 3), 5))
            c.add("TEL", val, 1)
        elif label in ("ID", "SECRET", "USERNAME", "CARD"):
            body = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._@#!$%*+/-" + (" " if label in ("ID", "CARD") else ""))
            start = n.AND(cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@"), vstart_at.at(-1))
            val = n.prop_right(start, n.AND(body, ~n.AND(sp, ~cls("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(1))), 5)
            if label in ("ID", "CARD"):
                val = n.AND(val, n.fill(val, digit, 5))
            c.add({"ID": "ID", "SECRET": "PASS", "USERNAME": "USERNAME", "CARD": "CARD"}[label], val, 1)
        elif label == "GIVENNAME":
            letter = n.OR(hanb, hangb, cyrb, latb, force=True)
            body = n.OR(letter, n.AND(sp, letter.at(1), letter.at(-1)), cls("."), force=True)
            start = n.AND(letter, vstart_at.at(-1))
            val = n.prop_right(start, body, 5)
            c.add("GIVENNAME", val, 1)
        elif label == "ADDRESS":
            start = n.AND(cls(allb.replace("\n", "").replace(" ", "")), vstart_at.at(-1))
            val = n.prop_right(start, nonl, 7)
            c.add("ADDRESS", val, 1)
        elif label == "BOD":
            body = cls("0123456789./- ") if True else None
            start = n.AND(digit, vstart_at.at(-1))
            val = n.OR(n.prop_right(start, n.OR(body, hanb, hangb, force=True), 5), force=True)
            c.add("BOD", n.AND(val, ~n.AND(sp, ~digit.at(1))), 1)

    # ---------- 1b. identifier keys whose value follows within a few bytes, without a colon ----------
    # "klantnummer is 77180342", "matricule 004517", "학번 30215", "IPP) est le 400187265", "RG 32.418.907-5"
    idk = tuple(k for k in KEYS["ID"] if len(k.encode()) >= 3) + ("matricule", "klantnummer", "personeelsnummer", "lidnummer", "polisnummer",
              "dossier", "IPP", "RG", "OAB", "学号", "学籍番号", "학번", "고객번호", "사번", "被保険者番号", "診察券番号", "N.º de processo", "processo",
              "табельный", "Табельный №", "№ полиса", "номер договора", "client n°", "n° client", "folio", "expediente", "NIA")
    idk_span, idk_end = P(G(*idk), pre="A-Za-z")
    gapc = n.OR(cls(" :=(\"'#.-"), cont, cls("\xef\xbc"), lits(("is", "est", "le", "es", "el", "é", "o", "nr", "n°", "N°", "no", "nº", "n.º", "№")), force=True)
    near_id = n.AND(n.OR(*[idk_end.at(-k) for k in range(1, 9)], force=True), nonl)
    idchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    id_start = n.AND(idchar, ~cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789").at(-1), near_id)
    id_val = n.prop_right(id_start, n.OR(idchar, n.AND(cls(" .-/"), idchar.at(1), idchar.at(-1)), force=True), 5)
    id_val = n.AND(id_val, n.fill(id_val, n.run(digit, 3), 5), ~n.fill(id_val, n.AND(id_val, cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(1), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(2), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(3), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(4), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZ").at(5)), 5))
    c.add("ID", id_val, 1)
    # ---------- 1c. account names in configuration syntax: DB_USER=guozh, user: nakamura_d, "usuario": "diegof_admin", login rkhabibullin
    uk_span, uk_end = P(G("USER", "user", "USERNAME", "username", "usuario", "utilisateur", "gebruiker", "usuário", "utilizador", "login", "логин", "Логин", "LOGIN"), pre="A-Za-z")
    ulow = cls("abcdefghijklmnopqrstuvwxyz0123456789._-")
    sep_u = n.OR(*[n.AND(uk_end.at(-len(x)), n.lit(x).at(-(len(x) - 1))) for x in ("=", ": ", ":", "\": \"", "\":\"", " = \"", "=\"", " ")], force=True)
    u_start = n.AND(cls("abcdefghijklmnopqrstuvwxyz"), sep_u.at(-1))
    u_val = n.prop_right(u_start, ulow, 5)
    _, login_end = P(G("login", "Login", "LOGIN", "логин", "Логин"), pre="A-Za-z")
    plain_space = n.AND(sp.at(-1), ~login_end.at(-2))       # a plain space separates a value only after "login" / "логин"
    u_val = n.AND(u_val, ~n.fill(u_val, n.AND(u_start, plain_space), 5), n.fill(u_val, n.AND(ulow, ~cls("abcdefghijklmnopqrstuvwxyz")), 5))   # a digit, _ . or - inside
    c.add("USERNAME", u_val, 1)

    # ---------- 2. names ----------
    hon_zh = lits(("先生", "女士", "小姐", "老师", "师傅", "經理", "经理", "总", "主任", "医生", "同学", "阿姨", "叔叔", "律师", "教授", "院长", "校长", "博士"))
    sur_zh = n.OR(lits(tuple(ZH_SURNAMES)), lits(ZH_COMPOUND), force=True)
    # a surname followed by 0-2 more Han characters, right before an honorific (王先生, 黄淑芬女士)
    for k in (1, 2, 3):
        L_ = 3 * k
        hit = n.AND(sur_zh, *[han_char.at(3 * j) for j in range(k)], hon_zh.at(L_))
        c.add("GIVENNAME", n.spread_right(hit, L_), 1)
    # a role word, then a surname and one or two characters (收货人刘建国, 配偶陈志明)
    role_zh_span, role_zh_end = P(G("收货人", "收件人", "联系人", "配偶", "负责人", "家长", "班主任", "配送员", "快递员", "客户", "患者", "同事",
                                     "老公", "老婆", "爱人", "表哥", "表姐", "表弟", "表妹", "堂哥", "堂姐", "朋友", "同学", "主管"))
    for k in (2, 3):
        L_ = 3 * k
        hit = n.AND(sur_zh, role_zh_end.at(-1), *[han_char.at(3 * j) for j in range(k)], ~han_char.at(L_) if k == 2 else han_char)
        c.add("GIVENNAME", n.spread_right(hit, L_), 1)
    # Japanese: kanji / katakana name before 様/さん/氏/先生/くん/ちゃん, not preceded by another kanji
    hon_ja = lits(("様", "さま", "さん", "氏", "先生", "くん", "君", "ちゃん", "殿", "医師", "部長", "課長", "係長"))
    prev_not_han = ~n.AND(han_lead.at(-3), cont.at(-2), cont.at(-1))
    for k in (1, 2, 3, 4):
        L_ = 3 * k
        hit = n.AND(han_char, prev_not_han, *[han_char.at(3 * j) for j in range(k)], hon_ja.at(L_))
        c.add("GIVENNAME", n.spread_right(hit, L_), 2)
    # self-introduction: "…の高橋です", "高橋と申します"
    intro_end = lits(("です", "と申します", "でございます"))
    for k in (1, 2, 3):
        L_ = 3 * k
        hit = n.AND(han_char, prev_not_han, *[han_char.at(3 * j) for j in range(k)], intro_end.at(L_), lits(("の", "、", "は")).at(-3))
        c.add("GIVENNAME", n.spread_right(hit, L_), 2)
    # Korean: a name token (surname + 1-3 syllables, a whole token) before an honorific or title
    hon_ko = lits(("씨", "님", "고객님", "선생님", "과장님", "부장님", "대리님", "팀장님", "교수님", "기사님", "사장님", "원장님", "과장", "부장", "대리", "팀장"))
    sur_ko = lits(tuple(KO_SURNAMES))
    not_ko = lits(KO_NOT_NAME)
    for k in (2, 3, 4):
        L_ = 3 * k
        hit = n.AND(sur_ko, ~not_ko, ~hang_char.at(-3), *[hang_char.at(3 * j) for j in range(k)], n.OR(hon_ko.at(L_), n.AND(sp.at(L_), hon_ko.at(L_ + 1)), force=True))
        c.add("GIVENNAME", n.spread_right(hit, L_), 1)
    # chat speakers in CJK: a surname-led label of 2-4 characters at a line start, before a colon
    colon = n.OR(cls(":"), n.lit("\xef\xbc\x9a"), force=True)
    line_start = n.OR(cls("\n").at(-1), n.lit("] ").at(-2), force=True)
    for k in (2, 3, 4):
        L_ = 3 * k
        for sur, ch in ((sur_zh, han_char), (sur_ko, hang_char)):
            hit = n.AND(sur, line_start, *[ch.at(3 * j) for j in range(k)], colon.at(L_), ~not_ko)
            c.add("GIVENNAME", n.spread_right(hit, L_), 1)
    # @mentions in any script
    at_ = n.AND(cls("@"), ~cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-").at(-1), cjk_char.at(1))
    c.add("USERNAME", n.prop_right(at_, n.OR(cls("@"), hanb, hangb, force=True), 5), 1)

    # Russian: patronymics, initials, honorifics, listed given names
    up_cyr = n.AND(cls("\xd0"), cls("\x81\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf").at(1))
    cyr_word_start = n.AND(up_cyr, ~cyrb.at(-1))
    cyr_word = n.prop_right(cyr_word_start, cyrb, 5)
    pat_end = lits(tuple(s + e for s in ("ович", "евич", "ьич", "овна", "евна", "ична", "инична") for e in ("", "а", "у", "ем", "ом", "е", "ой", "ы", "ей")))
    pat_word = n.fill(cyr_word, n.AND(pat_end, ~cyrb.at(len("ович".encode())) ), 5)
    # the patronymic word, the capitalised word before it, and a capitalised word before / after that
    c.add("GIVENNAME", pat_word, 1)
    w_before = n.fill(cyr_word, n.AND(cyr_word, ~cyrb.at(1), sp.at(1), n.AND(pat_word, up_cyr).at(2)), 5)
    w_before2 = n.fill(cyr_word, n.AND(cyr_word, ~cyrb.at(1), sp.at(1), n.AND(w_before, up_cyr).at(2)), 5)
    w_after = n.fill(cyr_word, n.AND(cyr_word_start, sp.at(-1), pat_word.at(-2)), 5)
    c.add("GIVENNAME", n.OR(w_before, w_before2, w_after, force=True), 1)
    # initials: "Р. А. Петренко", "Фёдорова Т. Н."
    init = n.AND(up_cyr, ~cyrb.at(-1), cls(".").at(2))
    after_init = n.fill(cyr_word, n.AND(cyr_word_start, n.OR(n.AND(sp.at(-1), init.at(-4)), n.AND(cls(".").at(-1), init.at(-3)), force=True)), 5)
    before_init = n.fill(cyr_word, n.AND(cyr_word, ~cyrb.at(1), sp.at(1), init.at(2)))
    init_mark = n.spread_right(n.AND(init, n.OR(after_init.at(4), after_init.at(3), before_init.at(-2), sp.at(-1) , force=True)), 3)
    c.add("GIVENNAME", n.OR(after_init, before_init, n.AND(init_mark, ~sp), force=True), 1)
    # honorifics and listed given names
    hon_ru_span, hon_ru_end = P(G("г-н ", "г-жа ", "Господин ", "Госпожа ", "господин ", "госпожа ", "Уважаемый ", "Уважаемая ", "Дорогой ", "Дорогая ", "врач ", "доктор "))
    c.add("GIVENNAME", n.fill(cyr_word, n.AND(cyr_word_start, hon_ru_end.at(-1)), 5), 1)
    ru_names = lits(tuple(nm[:-1] if nm[-1] in "ая" else nm for nm in RU_GIVEN))
    c.add("GIVENNAME", n.fill(cyr_word, n.AND(cyr_word_start, ru_names), 5), 2)

    # Latin-script languages: titles, greetings, introductions, relations, sign-offs, before a capitalised name
    cap = c.cap
    def name_after(frame_end):
        first = n.fill(cap, n.AND(c.wstart, frame_end.at(-1)), 5)
        second = n.fill(cap, n.AND(c.wstart, sp.at(-1), first.at(-2)), 5)
        part = n.OR(*[n.lit(" " + p + " ").at(1) for p in ("de", "da", "do", "dos", "das", "del", "van", "der", "den", "le", "du", "y")], force=True)
        third = n.fill(cap, n.AND(c.wstart, sp.at(-1), second.at(-2)), 5)
        return n.OR(first, second, third, force=True)
    frames = ("M. ", "Mme ", "Mlle ", "Monsieur ", "Madame ", "Mademoiselle ", "Me ", "Maître ", "Docteur ", "Dr ", "Dr. ", "Pr ", "Sr. ", "Sra. ", "Srta. ",
              "Don ", "Doña ", "Lic. ", "Licda. ", "Ing. ", "Dra. ", "Prof. ", "Profa. ", "Dona ", "Senhor ", "Senhora ", "dhr. ", "mevr. ", "mw. ",
              "Meneer ", "Mevrouw ", "De heer ", "Dhr. ", "Mevr. ", "Bonjour ", "Salut ", "Cher ", "Chère ", "Hola ", "Querido ", "Querida ", "Estimado ",
              "Estimada ", "Hallo ", "Hoi ", "Beste ", "Lieve ", "Olá ", "Oi ", "Caro ", "Cara ", "Prezado ", "Prezada ", "je m'appelle ", "Je m'appelle ",
              "je suis ", "me llamo ", "Me llamo ", "mi nombre es ", "soy ", "Soy ", "mijn naam is ", "ik ben ", "Ik ben ", "ik heet ", "meu nome é ",
              "Meu nome é ", "chamo-me ", "me chamo ", "mon mari ", "ma femme ", "mon fils ", "ma fille ", "mi esposo ", "mi esposa ", "mi marido ",
              "mi hijo ", "mi hija ", "tía ", "tío ", "mijn man ", "mijn vrouw ", "tante ", "oom ", "meu marido ", "minha esposa ", "tia ", "tio ",
              "avó ", "avô ", "abuela ", "abuelo ", "oma ", "opa ", "merci à ", "Merci à ", "gracias a ", "Gracias a ", "bedankt ", "obrigado ",
              "obrigada ", "llamen a ", "llama a ", "appelle ", "bel ", "liga para ", "fala com ", "habla con ", "parle à ", "praat met ", "demande à ",
              "pregunta a ", "con ", "avec ", "met ", "com ", "chez ")
    fr_span, fr_end = P(G(*frames), pre="A-Za-z0-9._@/\\-\x80-\xbf")
    job = lits(("Analyst", "Manager", "Director", "Engineer", "Developer", "Consultant", "Officer", "Associate", "Specialist", "Accountant",
                "Advisor", "Adviser", "Architect", "Designer", "Scientist", "Researcher", "Coordinator", "Administrator", "Assistant", "Executive",
                "Partner", "Lead", "Head", "Vice", "Software", "Data", "Product", "Project", "Account", "Sales", "Marketing", "Finance", "Team"))
    c.add("GIVENNAME", n.AND(name_after(fr_end), ~n.fill(cap, n.AND(c.wstart, job), 5)), 2)
    signoff = ("Cordialement", "Bien cordialement", "Bien à vous", "Bisous", "Amitiés", "Saludos", "Saludos cordiales", "Un saludo", "Atentamente",
               "Un abrazo", "Besos", "Met vriendelijke groet", "Met vriendelijke groeten", "Vriendelijke groet", "Groeten", "Groetjes", "Atenciosamente",
               "Cumprimentos", "Abraços", "Beijos", "С уважением", "Всего доброго")
    so_span, so_end = P(G(*signoff))
    nl_after = n.OR(*[n.AND(cls("\n").at(-k), so_end.at(-k - j)) for k in (1, 2) for j in (1, 2)], force=True)   # ",\n" / "\n\n"
    c.add("GIVENNAME", name_after(nl_after.at(1)), 1)
    c.add("GIVENNAME", n.fill(cyr_word, n.AND(cyr_word_start, nl_after), 5), 1)

    # ---------- 3. dates ----------
    for pat in (DIG + "{4}" + L("年") + DIG + "{1,2}" + L("月") + DIG + "{1,2}" + L("日"),
                G("令和", "平成", "昭和") + DIG + "{1,2}" + L("年") + DIG + "{1,2}" + L("月") + DIG + "{1,2}" + L("日"),
                DIG + "{1,2}" + L("月") + DIG + "{1,2}" + L("日"),
                DIG + "{4}" + L("년") + " ?" + DIG + "{1,2}" + L("월") + " ?" + DIG + "{1,2}" + L("일"),
                DIG + "{1,2}" + L("월") + " ?" + DIG + "{1,2}" + L("일"),
                DIG + "{1,2} " + G("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"),
                DIG + "{1,2} " + G("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"),
                DIG + "{1,2} de " + G("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
                                      "janeiro", "fevereiro", "março", "maio", "junho", "julho", "setembro", "outubro", "novembro", "dezembro"),
                DIG + "{1,2} " + G("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")):
        span, _ = P(pat, pre="0-9")
        c.add("DATE", span, 0)
        # ... with a year after it
        span2, _ = P(pat + G(" ", " de ") + DIG + "{4}", pre="0-9")
        c.add("DATE", span2, 0)

    # ---------- 4. phones in national formats ----------
    nd = "0-9+\\-"
    for pat in ("1[3-9][0-9]{9}", "1[3-9][0-9] [0-9]{4} [0-9]{4}", "1[3-9][0-9]\\-[0-9]{4}\\-[0-9]{4}",            # CN mobile
                "0[1-9][0-9]{1,2}\\-[0-9]{7,8}", "0[1-9][0-9]{1,2} [0-9]{4} [0-9]{4}",                              # CN landline
                "0[5789]0\\-[0-9]{4}\\-[0-9]{4}", "0[1-9][0-9]{0,3}\\-[0-9]{2,4}\\-[0-9]{4}",                          # JP
                "01[016789]\\-[0-9]{3,4}\\-[0-9]{4}", "01[016789][0-9]{7,8}",                                          # KR
                "8 \\([0-9]{3}\\) [0-9]{3}\\-[0-9]{2}\\-[0-9]{2}", "\\+7 \\([0-9]{3}\\) [0-9]{3}\\-[0-9]{2}\\-[0-9]{2}", "8[0-9]{10}",   # RU
                "0[1-9] [0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}", "0[1-9].[0-9]{2}.[0-9]{2}.[0-9]{2}.[0-9]{2}",            # FR
                "[67][0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}", "[67][0-9]{2} [0-9]{3} [0-9]{3}",                          # ES
                "06\\-[0-9]{8}", "06 [0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}", "06\\-[0-9]{2} [0-9]{2} [0-9]{2} [0-9]{2}",  # NL
                "9[1236][0-9] [0-9]{3} [0-9]{3}"):                                                                     # PT
        span, _ = P(pat, pre=nd, post=nd + "A-Za-z", start_terms=[~n.AND(sp.at(-1), digit.at(-2))])
        c.add("TEL", n.AND(span, ~n.fill(span, n.AND(span, sp, digit.at(1)), 5) if False else span), 1)
    # public hotlines are not personal: 400/800, 0120/0570/0800, 15xx/16xx/18xx, 8-800, 95xxx
    hot_span, _ = P("(400|800|0120|0570|0800|1588|1577|1544|1566|1600|1644|1661|1670|1688|1800|8 800|95)[0-9 \\-]{4,12}", pre=nd)
    c.hotline = hot_span

    # ---------- 5. national identifiers by shape ----------
    for pat, lab in (("[1-9][0-9]{5}(19|20)[0-9]{2}[01][0-9][0-3][0-9][0-9]{3}[0-9Xx]", "ID"),       # CN resident ID (date of birth inside)
                     ("[0-9]{2}[01][0-9][0-3][0-9]\\-[1-8][0-9]{6}", "ID"),                           # KR resident registration number
                     ("[0-9]{3}.[0-9]{3}.[0-9]{3}\\-[0-9]{2}", "ID"),                                  # BR CPF
                     ("[0-9]{8}\\-?[A-HJ-NP-TV-Z]", "ID"), ("[XYZ]\\-?[0-9]{7}\\-?[A-HJ-NP-TV-Z]", "ID"),      # ES DNI / NIE
                     ("[0-9]{3}\\-[0-9]{3}\\-[0-9]{3} [0-9]{2}", "ID"),                                # RU СНИЛС
                     ("[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[A-Z0-9][0-9]", "ID"),                              # MX CURP
                     ("[A-Z]{3,4}[0-9]{6}[A-Z0-9]{3}", "ID"),                                          # MX RFC
                     ("[12] [0-9]{2} [0-9]{2} [0-9]{2} [0-9]{3} [0-9]{3} [0-9]{2}", "ID"),            # FR NIR (spaced)
                     ("[0-9]{8} [0-9] [A-Z]{2}[0-9]", "ID"),                                           # PT Cartão de Cidadão
                     (G("京", "津", "沪", "渝", "冀", "豫", "云", "辽", "黑", "湘", "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋", "蒙", "陕", "吉",
                        "闽", "贵", "粤", "青", "藏", "川", "宁", "琼") + "[A-Z]" + "(\xc2\xb7)?" + "[A-Z0-9]{5,6}", "ID")):            # CN licence plate
        span, _ = P(pat, pre="0-9A-Za-z", post="0-9A-Za-z")
        c.add(lab, span, 1)
    # cue-only shapes: Russian passport after "паспорт / серия", ИНН 12 digits, BSN / NIF 9 digits
    cue_ru, cue_ru_end = P(G("паспорт", "Паспорт", "серия", "Серия", "ИНН", "BSN", "burgerservicenummer", "NIF", "contribuinte", "SNS", "utente"))
    reach = n.spread_right(cue_ru_end, 24)
    num = n.prop_right(n.AND(digit, ~digit.at(-1), reach), n.OR(digit, n.AND(cls(" ."), digit.at(1), digit.at(-1)), n.spread_right(n.lit(L("№")), 3), force=True), 4)
    c.add("ID", n.AND(num, n.fill(num, n.run(digit, 6), 4)), 1)

    # ---------- 6. addresses in national formats ----------
    for pat in (HANB + "{6,12}" + G("省", "市", "自治区") + "[\xe3-\xe9\x80-\xbf0-9A-Za-z\\-#]{6,90}" + G("号", "室", "栋", "幢", "单元", "楼", "座") + "[0-9A-Za-z\\-]{0,8}",
                G("東京都", "北海道", "京都府", "大阪府") + "[\xe3-\xe9\x80-\xbf]{3,40}" + DIG + "{1,4}" + G("-", "－") + DIG + "{1,4}" + "[0-9-]{0,5}",
                HANB + "{6,9}" + L("県") + "[\xe3-\xe9\x80-\xbf]{3,40}" + DIG + "{1,4}" + G("-", "－") + DIG + "{1,4}" + "[0-9-]{0,5}",
                G("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주") + HANGB + "{0,18} " + HANGB + "{3,15}"
                + G("구", "군", "시") + " " + "[\xea-\xed\x80-\xbf0-9]{3,24}" + G("로", "길", "동") + "( )?" + DIG + "{1,4}" + "[0-9-]{0,5}",
                G("ул. ", "улица ", "пр-т ", "проспект ", "пер. ", "наб. ", "бульвар ") + "[\xd0\xd1\x80-\xbf0-9 \\-]{2,40}" + G(", д. ", ", дом ") + DIG + "{1,4}",
                DIG + "{1,4}" + "(,)?" + " " + G("rue", "avenue", "boulevard", "impasse", "allée", "chemin", "cours", "place", "quai", "route") + " " + LATB.replace("]", " ]") + "{2,50}" + ", " + DIG + "{5} " + "[A-Z]" + LATB + "{2,30}",
                G("Calle ", "Avenida ", "Av. ", "Avda. ", "Carrera ", "Rua ", "Travessa ", "Praça ", "Alameda ") + LATB.replace("]", " ]") + "{2,40}" + "(,)?" + " " + DIG + "{1,5}" + "[A-Za-z0-9\xc3\x80-\xbf ,.'\\-#]{0,60}",
                "[A-Z]" + LATB + "{2,30}" + G("straat", "laan", "weg", "plein", "gracht", "kade", "singel", "dijk", "steeg", "hof", "pad") + " " + DIG + "{1,4}" + "[a-zA-Z]?"):
        try:
            span, _ = P(pat)
        except Exception:
            continue
        c.add("ADDRESS", span, 1)

    # ---------- 7. credentials and codes stated in a sentence ----------
    cred_span, cred_end = P(G("密码", "口令", "验证码", "取件码", "提货码", "动态码", "パスワード", "暗証番号", "認証コード", "確認コード", "비밀번호", "인증번호", "비번",
                               "пароль", "Пароль", "код подтверждения", "код доступа", "код домофона", "mot de passe", "digicode", "code d'accès",
                               "code d'activation", "code de retrait", "contraseña", "clave", "código", "wachtwoord", "toegangscode", "bezorgcode", "pincode",
                               "senha", "Senha", "Código"))
    copula = lits(("是", "为", "は", "은 ", "는 ", "는", "은", ": ", "：", " est ", " es ", " é ", " is ", " — ", "c'est "))
    near = n.spread_right(cred_end, 30)
    after_cop = n.fill(nonl, n.AND(copula, near), 3)
    vchar = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*_+-.")
    vstart = n.AND(vchar, ~vchar.at(-1), n.OR(after_cop.at(-1), n.AND(cls(" \"'").at(-1), after_cop.at(-2)), n.AND(n.lit(L("« ")).at(-3), after_cop.at(-4)), force=True), near)
    val = n.prop_right(vstart, n.OR(vchar, n.AND(sp, digit.at(1), digit.at(-1)), force=True), 5)
    c.add("PASS", n.AND(val, n.fill(val, digit, 5)), 1)
