-- Dark Seal (darksealj) QA 치트: 매 프레임 1P 무적·목숨·체력·마법 고정. 주소는 FBNeo support/cheats/darksealj.ini 기준.
-- FBNeo Lua 콘솔 창은 닫지 말고 최소화해 두세요(닫으면 스크립트가 멈춥니다).
emu.registerafter(function()
  memory.writebyte(0x10004B, 0xC0)   -- Invincibility PL1
  memory.writebyte(0x100036, 0x07)   -- Infinite Lives PL1
  memory.writebyte(0x100037, 0x0C)   -- Infinite Energy PL1
  memory.writebyte(0x10003E, 0x80)   -- Magic bar full PL1
end)
emu.message("QA cheat ON: 1P invincible / lives / energy / magic")
