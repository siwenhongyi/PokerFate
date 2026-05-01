local P = class("Notice", UiFullView)


function P:onAwake()
    self._openAnim, self._closeAnim = nil, "UI_common_notice_back"
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.TabTop = self:find("TabTop", self.Panel)
    self.TabList = self:find("TabList", self.Panel)
    self.Tab1Toggle = self:find("Tab1Toggle", self.TabList)
    self.Tab1Toggle:SetActive(false)

    self.Empty = self:find("Empty", self.Panel)
    self.ContentList = self:find("ContentList", self.Panel)
    self.Content = self:find("Viewport/Content", self.ContentList)
    self.ImageTitle = self:find("ImageTitle", self.ContentList)
    -- self.TextTitle = self:find("ImageTitle/TextTitle", self.Content)
    self.ImageBanner = self:find("ImageBanner", self.ContentList)
    self.TextTips = self:find("TextTips", self.ContentList)
    self.ImageTitle:SetActive(false)
    self.ImageBanner:SetActive(false)
    self.TextTips:SetActive(false)

    self.TabToggles = {
        [NoticeModel.NOTICE_TYPE.Activity] = self:find("Tab1Toggle", self.TabTop),
        [NoticeModel.NOTICE_TYPE.System] = self:find("Tab2Toggle", self.TabTop),
    }
    for k, v in pairs(self.TabToggles) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_tab_switch_1")
                self:showNotice(k)
                bee.logEvent(1 == k and "notice-event" or "notice-system")
            end
        end)
    end

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)

    RedManager:bind(self:find("Reddot", self.TabToggles[NoticeModel.NOTICE_TYPE.Activity]), RedTag.NoticeActivity)
    RedManager:bind(self:find("Reddot", self.TabToggles[NoticeModel.NOTICE_TYPE.System]), RedTag.NoticeSystem)

    self.ListTab = UiListEx:create(self.TabList)
    self.ListTab:setWidth(130)
    self.ListTab:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Tab1Toggle)
    end)
    self.ListTab:setRefreshFunc(function(data, item)
        self:refreshTabItem(data, item)
    end)
end

function P:onShow()
    NoticeModel:reqNoticeList(function()
        -- self:showNotice(self._notice_type)
    end)
    local notice_type = self._params and self._params.notice_type or NoticeModel.NOTICE_TYPE.Activity
    self:showNotice(notice_type, self._params and self._params.id)

    if notice_type == NoticeModel.NOTICE_TYPE.System then
        bee.setCheck(self.TabToggles[notice_type], false)
    end
end

function P:showNotice(notice_type, noticeId)
    self._notice_type = notice_type
    local info = NoticeModel:getInfo(self._notice_type)

    self.Empty:SetActive(#info.list == 0)
    self.TabList:SetActive(#info.list > 0)
    self.ContentList:SetActive(#info.list > 0)

    self._select_data = info.list[1]
    if noticeId then
        for _, v in ipairs(info.list) do
            if v.id == noticeId then
                self._select_data = v
                break
            end
        end
    end
    self.ListTab:setDatas(info.list)
    self:refreshContent()
end

function P:refreshTabItem(data, item)
    local TextTitle1 = self:find("TextTitle1", item)
    local TextTitle2 = self:find("TextTitle2", item)

    if self._select_data == data then
        TextTitle1:SetActive(false)
        TextTitle2:SetActive(true)
        self:find("On", item):SetActive(true)
        self:find("Off", item):SetActive(false)
        self:find("Selected", item):SetActive(true)
        
        local tab = data.tab
        if LanguageManager:getLanguage() ~= "en" then
            tab = string.gsub(tab, " ",  Config.NO_WRAP_SPACE)
        end
        bee.setText(TextTitle2, _T(tab))
        NoticeModel:setIsRead(data.id)
    else
        TextTitle1:SetActive(true)
        TextTitle2:SetActive(false)
        self:find("On", item):SetActive(false)
        self:find("Off", item):SetActive(true)
        self:find("Selected", item):SetActive(false)

        local tab = data.tab
        if LanguageManager:getLanguage() ~= "en" then
            tab = string.gsub(tab, " ",  Config.NO_WRAP_SPACE)
        end
        bee.setText(TextTitle1, _T(tab))
    end
    self:find("Reddot", item):SetActive(not NoticeModel:isReaded(data.id))
    bee.addClick(item, function()
        Game:playSound("ui_tab_switch_2")
        if self._select_data ~= data then
            self:setSelectData(data)
            bee.logEvent("notice-tag", data.id)
        end
    end, true)
end

function P:refreshContent()
    if not self._select_data then
        self.ContentList:SetActive(false)
        return
    end
    self.ContentList:SetActive(true)
    self:removeAllChildren(self.Content)
    local title = CU.GameObject.Instantiate(self.ImageTitle, self.Content.transform, false)
    title:SetActive(true)
    bee.setText(self:find("TextTitle", title), _T(self._select_data.title))

    local textList = GF.parseLinks(self._select_data.content)
    for _, v in ipairs(textList) do
        if v ~= "" then
            if string.find(v, "<img>") then
                local url = string.match(v, "<img>(.*)</img>")
                local href = string.match(v, 'href="(.*)"')
                if url then
                    local item = CU.GameObject.Instantiate(self.ImageBanner, self.Content.transform, false)
                    item:SetActive(true)
                    -- item:GetComponent("LoadImage"):DownloadImage(url)
                    bee.getDownloadImage(item, url)
                    if href then
                        bee.addClick2(item, function()
                            GF.onClickLink(href)
                        end)
                    end
                end
            else
                local dts = string.gmatch(v, '<dt format="([^"]*)">(.-)</dt>')
                for k, vv in dts do
                    local kk = string.gsub(k, "%%", "%%%%")
                    kk = string.gsub(kk, "%-", "%%-")
                    v = string.gsub(v, string.format('<dt format="%s">%s</dt>', kk, vv), os.date(k, tonumber(vv)))
                end
                local item = CU.GameObject.Instantiate(self.TextTips, self.Content.transform, false)
                item:SetActive(true)
                item:GetComponent("HyperlinkText"):AddListener(function(href)
                    GF.onClickLink(string.gsub(href, '"', ''))
                end)
                if LanguageManager:getLanguage() ~= "en" then
                    v = string.gsub(v, " ",  Config.NO_WRAP_SPACE)
                end
                bee.setText(item, v, "HyperlinkText")
            end
        end
    end
    self.ContentList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
end

function P:setSelectData(data)
    if self._select_data then
        local tmp = self._select_data
        self._select_data = nil
        self.ListTab:refreshDataItem(tmp)
    end
    self._select_data = data
    self.ListTab:refreshDataItem(self._select_data)
    self:refreshContent()
end

function P:evt_noticeRefresh()
    self:showNotice(self._notice_type, self._select_data and self._select_data.id)
end

return P