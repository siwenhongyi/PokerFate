local P = class("LevelUnlock", UiDialog)

function P:onAwake()
    self.Unlock = self:find("AnimRoot/Center/Unlock")

    self.ImageIcon = self:find("ImageIcon", self.Unlock)
    self.TextName = self:find("TextName", self.Unlock)
    self.TextDec = self:find("TextDec", self.Unlock)

    bee.addClick(self:find("CloseMask", self.Unlock), function()
        self:hideUI()
    end)

    Game:playSound("ui_level_unlock")
end

function P:onShow()
    if self._params and self._params.ids then
        for _, v in ipairs(self._params.ids) do
            local info = tpl_system_info[v]
            if info then
                bee.setIcon(self.ImageIcon, info.icon)
                bee.setText(self.TextName, _T(info.name))
                bee.setText(self.TextDec, _T(info.dec))
                break
            end
        end
    end
end

return P