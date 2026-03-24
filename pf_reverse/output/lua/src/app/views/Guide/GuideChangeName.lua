local P = class("GuideChangeName", UiBase)


function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    local Panel = self:find("Panel", Center)

    self.NameInput = self:find("NameInput", Panel)
    self.TextTip = self:find("TextTip", Panel)
    self.TextName = self:find("TextName", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Panel), function()
        local name = bee.getText(self.NameInput, "InputField")
        if not GF.isValidName(name, self.TextTip) then
            return
        end
        self:reqChangeName(name)
    end)
    bee.addClick(self:find("AutoButton", Panel), function()
        Net:post("/newbie/nickname", {lang = LanguageManager:getLanguage()}, function(d)
            if 0 == d.code then
                bee.setText(self.NameInput, d.nickname, "InputField")
            end
        end)
        bee.logEvent("guide-nickname-random")
    end)
end

function P:onShow()
end

function P:onHide()
    GuideManager:doGuideStep()
end

function P:reqChangeName(name)
    Net:post("/newbie/setNickname", {nickname = GF:getValidString(name)}, function(d)
        if 0 == d.code then
            PlayerModel:setName(name)
            self:hideUI()
            bee.emit(EventDef.evt_refreshName)
        else
            local e = tpl_errorCode[d.code]
            if e and e.tip ~= 0 then
                bee.setText(self.TextTip, _T(e.id))
            end
        end
    end, nil, true)
end

