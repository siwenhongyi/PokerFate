local P = class("InGameShortcutKey", Object)

function P:onStart()
    self.actionLayer = UiManager:getUI("PKActionLayer")
    self.actionAllInLayer = UiManager:getUI("PKActionAllinLayer")
    self.actionView = self.actionLayer or self.actionAllInLayer

end

function P:onUpdate()
    if CU.Input.GetKeyDown(CU.KeyCode.A) then
        if self:checkShowable() then
            self.actionView:allinEvent()
        end
    end

    if CU.Input.GetKeyDown(CU.KeyCode.F) then
        if self:checkShowable() then
            self.actionView:foldEvent()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.C) then
        if self:checkShowable() then
            self.actionView:callEvent()
        end
    end
    if (CU.Input.GetKey(CU.KeyCode.LeftShift) or CU.Input.GetKey(CU.KeyCode.RightShift)) 
        and CU.Input.GetKeyDown(CU.KeyCode.C) then
        if self:checkShowable() then
            self.actionView:callAnyEvent()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.Space) then
        if self:checkShowable() then
            self.actionView:checkEvent()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.B) then
        if self:checkShowable() then
            self.actionView:batEvent()
        end
    end
    if CU.Input.GetKeyDown(CU.KeyCode.R) then
        if self:checkShowable() then
            self.actionView:raiseEvent()
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

    local uiName = ShortcutKeyManager:getTopestViewName()
    return uiName == self.actionView.node.name
end

return P