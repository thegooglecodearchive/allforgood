# -*- coding: UTF-8 -*-

UTF8_MAP = { 
  u"¡": u"!", u"¢": u"c", u"£": u"L", u"¤": u"o", u"¥": u"Y",
  u"¦": u"|", u"§": u"S", u"¨": u"`", u"©": u"c", u"ª": u"a",
  u"«": u"<<", u"¬": u"-", u"­": u"-", u"®": u"R", u"¯": u"-",
  u"°": u"o", u"±": u"+-", u"²": u"2", u"³": u"3", u"´": u"'",
  u"µ": u"u", u"¶": u"P", u"·": u".", u"¸": u",", u"¹": u"1",
  u"º": u"o", u"»": u">>", u"¼": u"1/4", u"½": u"1/2", u"¾": u"3/4",
  u"¿": u"?", u"À": u"A", u"Á": u"A", u"Â": u"A", u"Ã": u"A",
  u"Ä": u"A", u"Å": u"A", u"Æ": u"Ae", u"Ç": u"C", u"È": u"E",
  u"É": u"E", u"Ê": u"E", u"Ë": u"E", u"Ì": u"I", u"Í": u"I",
  u"Î": u"I", u"Ï": u"I", u"Ð": u"D", u"Ñ": u"N", u"Ò": u"O",
  u"Ó": u"O", u"Ô": u"O", u"Õ": u"O", u"Ö": u"O", u"×": u"*",
  u"Ø": u"O", u"Ù": u"U", u"Ú": u"U", u"Û": u"U", u"Ü": u"U",
  u"Ý": u"Y", u"Þ": u"p", u"ß": u"b", u"à": u"a", u"á": u"a",
  u"â": u"a", u"ã": u"a", u"ä": u"a", u"å": u"a", u"æ": u"ae",
  u"ç": u"c", u"è": u"e", u"é": u"e", u"ê": u"e", u"ë": u"e",
  u"ì": u"i", u"í": u"i", u"î": u"i", u"ï": u"i", u"ð": u"d",
  u"ñ": u"n", u"ò": u"o", u"ó": u"o", u"ô": u"o", u"õ": u"o",
  u"ö": u"o", u"÷": u"/", u"ø": u"o", u"ù": u"u", u"ú": u"u",
  u"û": u"u", u"ü": u"u", u"ý": u"y", u"þ": u"p", u"ÿ": u"y", 
  u"’": u"'",
}

def asciify(error):
  return UTF8_MAP[error.object[error.start]], error.end

