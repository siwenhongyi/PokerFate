local P = class("SettingFeedback", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.BgView = self:find("BgView", self.Panel)

    self.Buttons = {
        [MediaPlatform.Discord] = self:find("DiscordButton", self.BgView),
        [MediaPlatform.QQ] = self:find("qqButton", self.BgView),
        [MediaPlatform.X] = self:find("xButton", self.BgView),
        [MediaPlatform.Facebook] = self:find("FacebookButton", self.BgView),
        [MediaPlatform.Line] = self:find("LineButton", self.BgView),
        [MediaPlatform.Bilili] = self:find("BililiButton", self.BgView),
    }

    for _, v in pairs(self.Buttons) do
        v:SetActive(false)
    end

    local curLang = LAN:getLanguage()
    for k, v in ipairs(tpl_medialink_config_list) do
        if self.Buttons[v.media_id] then
            if v.lang == curLang then
                if self.Buttons[v.media_id] then
                    self.Buttons[v.media_id]:SetActive(true)
                    bee.addClick(self.Buttons[v.media_id], function()
                        if v.link then
                            bee.openUrl(v.link)
                        elseif v.copytext then
                            CS.SdkHelper.copyText(v.copytext)
                            UiManager:showToast(_T("LAB_COPY_SUC"))
                        end
                        self:hideUI()
                    end, true)
                end
            else
                -- self.Buttons[v.media_id]:SetActive(false)
            end
        end
    end

    bee.addClick(self:find("CopyButton", self.Panel), function()
        CS.SdkHelper.copyText(_T("LAB_SERVICE_EMAIL"))
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

