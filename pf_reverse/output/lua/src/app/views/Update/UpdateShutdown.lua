local P = class("UpdateShutdown", UiDialog)


function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    self.TextTip = self:find("TextTip", Panel)
    self.TextTitle = self:find("TextTitle", Panel)
    self.TextTime = self:find("TextTime", Panel)
    self.TextTimeTitle = self:find("TextTimeTitle", Panel)
    self.UpdateButton = self:find("UpdateButton", Panel)

    bee.addClick(self.UpdateButton, function()
        if self._params and self._params.onSure then
            self._params.onSure()
        end
        self:hideUI()
    end)
end

function P:onShow()
    if self._params then
        if self._params.title then
            bee.setText(self.TextTitle, self._params.title)
        end
        bee.setText(self.TextTip, self._params.text or "")
        if self._params.surStr then
            bee.setText(self:find("Text", self.UpdateNowButton), self._params.surStr)
            bee.setText(self:find("Text", self.UpdateButton), self._params.surStr)
        end
        if self._params.cancelStr then
            bee.setText(self:find("Text", self.NotUpdateButton), self._params.cancelStr)
        end

        if self._params.data then
            local data = self._params.data
            bee.setText(self.TextTime, _F("{p1} - {p2}", TimeHelp:getDateTimeStr(data.start_time or bee.getServerTime()), TimeHelp:getDateTimeStr(data.end_time or bee.getServerTime())))
        else
            self.TextTimeTitle:SetActive(false)
            self.TextTime:SetActive(false)
        end
    end
    bee.logEvent("login-update-shut-show")
end

