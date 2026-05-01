-- 界面
local P = class("UiScene", require("ui.UiBase"))
UiScene = P

function P:onEnter()
    print("[UiScene] onEnter", self.__cname)
    self:addAutoEvent()
end

function P:onExit()
    print("[UiScene] onExit", self.__cname)
    self:removeAutoEvent()
end

return P