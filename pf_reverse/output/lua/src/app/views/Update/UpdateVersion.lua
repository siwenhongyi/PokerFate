local P = class("UpdateVersion", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    self.TextTip = self:find("TextTip", Panel)
    self.TextTitle = self:find("TextTitle", Panel)
    self.NotUpdateButton = self:find("NotUpdateButton", Panel)
    self.UpdateNowButton = self:find("UpdateNowButton", Panel)
    self.UpdateButton = self:find("UpdateButton", Panel)

    self.Update_img_pic_01 = self:find("Pic/Update_img_pic_01", Panel)

    bee.addClick(self.NotUpdateButton, function()
        self:hideUIForce()
        bee.logEvent("login-update-cancel")
        if self._params and self._params.onCancel then
            self._params.onCancel()
        end
    end)
    bee.addClick(self.UpdateNowButton, function()
        self:hideUIForce()
        bee.logEvent("login-update-immediately")
        if self._params and self._params.onSure then
            self._params.onSure()
        end
    end)
    bee.addClick(self.UpdateButton, function()
        self:hideUIForce()
        bee.logEvent("login-update-immediately")
        if self._params and self._params.onSure then
            self._params.onSure()
        end
    end)
end

function P:onShow()
    if self._params then
        if self._params.button == 1 then
            self.NotUpdateButton:SetActive(false)
            self.UpdateNowButton:SetActive(false)
            self.UpdateButton:SetActive(true)
        else
            self.NotUpdateButton:SetActive(true)
            self.UpdateNowButton:SetActive(true)
            self.UpdateButton:SetActive(false)
        end
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
    end

    Net:post("/open/newVersionPicture", {lang = LanguageManager:getLanguage()}, function(d)
        if d and d.code == 0 and d.image_url and "" ~= d.image_url then
            -- self.Update_img_pic_01:GetComponent("LoadImage"):DownloadImage(d.image_url)
            bee.getDownloadImage(self.Update_img_pic_01, d.image_url)
        end
    end)
end

return P