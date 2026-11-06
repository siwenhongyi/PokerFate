local P = class("LobbyShortcutKey", Object)

function P:onStart()
    self.lobbyLayer = UiManager:getUI("LobbyLayer")
end

function P:onUpdate()
    if CU.Input.GetKeyDown(CU.KeyCode.F1) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutSetting()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.B) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutBackpack()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.C) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutCharacter()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.T) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutTask()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.M) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutMail()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.S) then
        if self:checkShowable() then
            self.lobbyLayer:ShortcutShop()
        end
    end
end

function P:checkShowable()
    --版本过低无效
    if not bee.checkVersion("1.6.4") then
		return
	end

    --引导快捷键无效
	if GuideManager:isInGuide() then
		return false
	end

    --主界面屏蔽UI快捷键无效
    if self.lobbyLayer:getUIVisibleSign() then
        return false
    end

    local uiName = ShortcutKeyManager:getTopestViewName()
    return uiName == self.lobbyLayer.node.name
end

return P