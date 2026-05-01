local P = class("EmailMain", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.TextUnRead = self:find("TextUnRead", self.Center)
    self.TextRecv = self:find("TextRecv", self.Center)
    self.DeleteReadButton = self:find("DeleteReadButton", self.Center)
    self.ClaimAllButton = self:find("ClaimAllButton", self.Center)
    self.EmailList = self:find("EmailList", self.Center)
    self.Item1 = self:find("Item1", self.EmailList)
    self.Item1:SetActive(false)

    self.EmailEmpty = self:find("EmailEmpty", self.Center)
    self.EmailDetail = self:find("EmailDetail", self.Center)
    self.ClaimButton = self:find("ClaimButton", self.EmailDetail)
    self.DeleteButton = self:find("DeleteButton", self.EmailDetail)
    self.StarOnButton = self:find("StarOnButton", self.EmailDetail)
    self.StarOffButton = self:find("StarOffButton", self.EmailDetail)
    self.TextTitle = self:find("TextTitle", self.EmailDetail)
    self.TextFrom = self:find("TextFrom", self.EmailDetail)
    self.TextTime = self:find("TextTime", self.EmailDetail)
    self.ContentSmall = self:find("ContentSmall", self.EmailDetail)
    self.ContentBig = self:find("ContentBig", self.EmailDetail)
    self.TextContentSmall = self:find("ContentSmall/Viewport/Content/TextContent", self.EmailDetail)
    self.TextContentBig = self:find("ContentBig/Viewport/Content/TextContent", self.EmailDetail)

    self.EmailAttachment = self:find("EmailAttachment", self.Center)
    self.AttachmentItem1 = self:find("Item1", self.EmailAttachment)
    self.AttachmentItem1:SetActive(false)
    self.AttachView = self:find("AttachList/Viewport/Content", self.EmailAttachment)

    local Tab = self:find("Tab", self.Center)
    self.TabToggles = {
        self:find("Tab1Toggle", Tab),
        self:find("Tab2Toggle", Tab),
    }
    for k, v in pairs(self.TabToggles) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_tab_switch_1")
                self:showMailType(k - 1)
                bee.logEvent(k == 1 and "mail-regular" or "mail-special")
            end
        end)
    end

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)

    bee.addClick(self.DeleteReadButton, function()
        if self:find("On", self.DeleteReadButton).activeSelf then
            UiManager:showTip({
                text = _T("LAB_MAIL_006"),
                onSure = function()
                    EmailModel:reqDelEamil(nil, self._mail_type, true, function()
                        self:showMailType(self._mail_type)
                    end)
                end,
            })
        else
            UiManager:showToast(_T("LAB_MAIL_008"))
        end
        bee.logEvent("mail-delete-all")
    end)

    bee.addClick(self.ClaimAllButton, function()
        Game:playSound("ui_button_confirm")
        if self:find("On", self.ClaimAllButton).activeSelf then
            EmailModel:reqEamilAttach(nil, self._mail_type, true, function(data)
                if #data.item_list > 0 then
                    UiManager:showUI("BackpackClaimResult", {
                        items = data.item_list
                    })
                end
                self.ListEmail:refreshShowingUi()
                self:refreshMailNum()
                self:refreshEmailDetail()
            end)
        else
            UiManager:showToast(_T("LAB_MAIL_009"))
        end
        bee.logEvent("mail-claim-all")
    end)

    bee.addClick(self.DeleteButton, function()
        Game:playSound("ui_button_confirm")
        local data = EmailModel:getDetail(self._select_id)
        if data then
            if data.coll_type == 1 then
                UiManager:showTip({
                    text = _T("LAB_MAIL_012"),
                    onSure = function()
                        self:doDelMail()
                    end,
                })
            else
                self:doDelMail()
            end
        end
    end)

    bee.addClick(self.ClaimButton, function()
        EmailModel:reqEamilAttach({self._select_id}, self._mail_type, nil, function(data)
            if data.item_list and #data.item_list > 0 then
                UiManager:showUI("BackpackClaimResult", {
                    items = data.item_list
                })
                self:refreshEmailDetail()
                self:refreshMailNum()
            end
        end)
    end)

    bee.addClick(self.StarOnButton, function()
        EmailModel:reqCollEamil({self._select_id}, true, function()
            self:refreshCurItem()
            UiManager:showToast(_T("LAB_MAIL_027"))
        end)
        local f3 = 0
        if not self._select_data.system_mail_id or 0 == self._select_data.system_mail_id then
            f3 = 1
        end
        bee.logEvent("mail-collection", 0, self._select_id, f3, self._mail_type)
    end)
    bee.addClick(self.StarOffButton, function()
        EmailModel:reqCollEamil({self._select_id}, false, function()
            self:refreshCurItem()
            UiManager:showToast(_T("LAB_MAIL_026"))
        end)
        local f3 = 0
        if not self._select_data.system_mail_id or 0 == self._select_data.system_mail_id then
            f3 = 1
        end
        bee.logEvent("mail-collection", 1, self._select_id, f3, self._mail_type)
    end)

    self.ListEmail = UiListEx:create(self.EmailList)
    self.ListEmail:setWidth(140)
    self.ListEmail:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListEmail:setRefreshFunc(function(data, item)
        self:refreshEmailItem(data, item)
    end)
    self.ListEmail:addValueChanged(function()
        local shows = self.ListEmail:getShows()
        local count = self.ListEmail:getDatasCount()
        for _, v in ipairs(shows) do
            if v == count then
                EmailModel:reqNextEmailList(self._mail_type, function(data, mail_type)
                    if mail_type == self._mail_type and data.list then
                        self.ListEmail:append(data.list)
                    end
                end)
            end
        end
    end)

    RedManager:bind(self:find("Reddot", self.TabToggles[1]), RedTag.EmailNormal)
    RedManager:bind(self:find("Reddot", self.TabToggles[2]), RedTag.EmailSpecial)
end

function P:onShow()
    local n1, n2 = EmailModel:getRedCount(EmailModel.MAIL_TYPE.Normal), EmailModel:getRedCount(EmailModel.MAIL_TYPE.Special)
    if n1 > 0 or n2 <= 0 then
        self:showMailType(EmailModel.MAIL_TYPE.Normal)
    else
        self:showMailType(EmailModel.MAIL_TYPE.Special)
        bee.setCheck(self.TabToggles[2], false, true)
    end

    -- local info = EmailModel:getInfo(self._mail_type)
    -- if info.total >= math.ceil(tpl_constdata.Email_Warning * tpl_constdata.EmailCountLimit / 100) then
    --     UiManager:showTip({text = _T("LAB_MAIL_014"), button = 1})
    -- end

    -- self:schedule(10, function()
    -- end)
end

function P:refreshMailList()
    local info = EmailModel:getInfo(self._mail_type)
    EmailModel:reqEmailList(self._mail_type, 0, function(data)
        if info.mail_type == self._mail_type then
            local curSel = self._select_id
            self._select_id, self._select_data = nil, nil
            if curSel then
                for _, v in ipairs(info.list) do
                    if v.id == curSel then
                        self._select_id = v.id
                        self._select_data = v
                        break
                    end
                end
            end
            if not self._select_id then
                self:setSelectData(info.list[1], true)
            end
            self:refreshMailInfo()
            self.ListEmail:setDatas(info.list)
            self:refreshEmailDetail()
        end
    end)
end

function P:showMailType(mail_type)
    self._mail_type = mail_type
    self:refreshMailInfo()
    local info = EmailModel:getInfo(self._mail_type)
    EmailModel:reqEmailList(self._mail_type, 0, function(data)
        if info.mail_type == self._mail_type then
            self:setSelectData(info.list[1], true)
            self:refreshMailInfo()
            self.ListEmail:setDatas(info.list)
            self.ListEmail:moveToYItem(1)
            self:refreshEmailDetail()
        end
    end)
end

function P:setSelectData(data, noUi)
    local oldData = self._select_data
    if data then
        self._select_id, self._select_data = data.id, data
    else
        self._select_id, self._select_data = nil, nil
    end
    if not noUi then
        self.ListEmail:refreshShowingUi()
    end
end

function P:refreshMailNum()
    local info = EmailModel:getInfo(self._mail_type)
    bee.setText(self.TextRecv, string.format("%s<color=#EE9E00>%d</color>", _T("LAB_MAIL_018"),info.total, tpl_constdata.EmailCountLimit))
    bee.setText(self.TextUnRead, _T("LAB_MAIL_001") .. info.unread_total)

    self:find("On", self.DeleteReadButton):SetActive(info.del_total > 0)
    self:find("Off", self.DeleteReadButton):SetActive(info.del_total == 0)

    self:find("On", self.ClaimAllButton):SetActive(info.item_total > 0)
    self:find("Off", self.ClaimAllButton):SetActive(info.item_total == 0)
end

function P:refreshMailInfo()
    local info = EmailModel:getInfo(self._mail_type)

    self:refreshMailNum()
    self.EmailEmpty:SetActive(#info.list == 0)
    self.EmailList:SetActive(#info.list > 0)
    self.DeleteReadButton:SetActive(#info.list > 0)
    self.ClaimAllButton:SetActive(#info.list > 0)
    self.EmailDetail:SetActive(#info.list > 0)
    self.EmailAttachment:SetActive(false)
end

function P:refreshEmailItem(data, item)
    if not self._select_id then
        self:setSelectData(data)
        self:refreshEmailDetail()
    end
    local ItemOn, ItemOff = self:find("ItemOn", item), self:find("ItemOff", item)
    local CurItem = ItemOff
    if self._select_id == data.id then
        ItemOn:SetActive(true)
        ItemOff:SetActive(false)
        CurItem = ItemOn
    else
        ItemOn:SetActive(false)
        ItemOff:SetActive(true)
    end

    bee.setTextCut(self:find("TextTitle", CurItem), EmailModel:getEmailTitle(data), 465)
    -- bee.setText(self:find("TextFrom", CurItem), EmailModel:getFromName(data))
    -- bee.setText(self:find("TextDate", CurItem), TimeHelp:getDateTimeStr(data.display_time))
    
    bee.setText(self:find("TextFrom", CurItem), TimeHelp:getDateTimeStr(data.display_time))
    if self._mail_type == EmailModel.MAIL_TYPE.Special or data.coll_type == 1 or (data.has_item and data.status ~= EmailModel.STATUS.UserMailStatusReadReceived) then
        bee.setText(self:find("TextDate", CurItem), "")
    else
        local day = 30 - math.ceil((bee.getServerTime() - data.display_time) / 86400)
        if day < 1 then
            day = 1
        end
        bee.setText(self:find("TextDate", CurItem), _F("LAB_MAIL_029", day))
    end
    self:find("ImageStar", CurItem):SetActive(data.coll_type == 1)
    
    if data.status == EmailModel.STATUS.UserMailStatusUnread then
        bee.setIcon(self:find("ImageRead", CurItem), "Email[email_icon_unread]", true)
        self:find("Reddot", item):SetActive(true)
    else
        bee.setIcon(self:find("ImageRead", CurItem), "Email[email_icon_read]", true)
        self:find("Reddot", item):SetActive(data.status == EmailModel.STATUS.UserMailStatusReadNotReceived)
    end
    if data.role_id and data.role_id > 0 then
        bee.find("Avatar", item):SetActive(true)
        self:find("ImageRead", CurItem):SetActive(false)
        local ds = get_tpl_subKey(tpl_character_skin_list, "role", data.role_id)
        if #ds > 0 then
            CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon"), ds[1].id)
        end
    else
        bee.find("Avatar", item):SetActive(false)
        self:find("ImageRead", CurItem):SetActive(true)
    end

    self:find("TextTitle/ImageAttach", CurItem):SetActive(data.has_item)

    bee.addClick(item, function()
        Game:playSound("ui_tab_switch_2")
        if item.status == EmailModel.STATUS.UserMailStatusUnread then
            item.status = EmailModel.STATUS.UserMailStatusRead
        end
        if self._select_id ~= data.id then
            self:setSelectData(data)
            self:refreshEmailItem(data, item)
            self:refreshEmailDetail()
        end
    end, true)
end

function P:refreshCurItem()
    local item = self.ListEmail:getDataNode(self._select_data)
    if item then
        self:refreshEmailItem(self._select_data, item)
    end
    self:refreshEmailDetail()
end

function P:refreshEmailDetail()
    if not self._select_id then
        self.EmailDetail:SetActive(false)
        self.EmailAttachment:SetActive(false)
        return
    end
    EmailModel:reqEmailDetail(self._select_id, function(data)
        self:refreshMailNum()
        self.EmailDetail:SetActive(true)
        bee.setText(self.TextTitle, EmailModel:getEmailTitle(data))
        bee.setText(self.TextFrom, _T("LAB_MAIL_025") .. EmailModel:getFromName(data))
        bee.setText(self.TextTime, TimeHelp:getDateTimeStr(data.display_time))

        self.StarOnButton:SetActive(1 == data.coll_type)
        self.StarOffButton:SetActive(1 ~= data.coll_type)

        if data.item_list and #data.item_list > 0 then
            self.EmailAttachment:SetActive(true)
            bee.setText(self.TextContentSmall, EmailModel:getEamilContent(data))
            self.ContentSmall:SetActive(true)
            self.ContentBig:SetActive(false)
        else
            self.EmailAttachment:SetActive(false)
            bee.setText(self.TextContentBig, EmailModel:getEamilContent(data))
            self.ContentSmall:SetActive(false)
            self.ContentBig:SetActive(true)
        end
        if data.item_list and #data.item_list > 0 then
            self:removeAllChildren(self.AttachView)
            for _, v in ipairs(data.item_list) do
                local attach = CU.GameObject.Instantiate(self.AttachmentItem1, self.AttachView.transform, false)
                attach:SetActive(true)
                PropItem:create(attach, v):bindTips()
                self:find("ImageGet", attach):SetActive(data.status == EmailModel.STATUS.UserMailStatusReadReceived)
                self:find("Mask", attach):SetActive(data.status == EmailModel.STATUS.UserMailStatusReadReceived)
            end
            if data.status == EmailModel.STATUS.UserMailStatusReadNotReceived then
                self.ClaimButton:SetActive(true)
                self.DeleteButton:SetActive(false)
            else
                self.ClaimButton:SetActive(false)
                self.DeleteButton:SetActive(true)
            end
        else
            self.ClaimButton:SetActive(false)
            self.DeleteButton:SetActive(true)
        end
        local item = self.ListEmail:getDataNode(self._select_data)
        if item then
            self:refreshEmailItem(self._select_data, item)
        end
    end)
end

function P:doDelMail()
    EmailModel:reqDelEamil({self._select_id}, self._mail_type, nil, function(data, mail_type)
        -- self:setSelectData(nil)
        if self._mail_type == mail_type then
            self.ListEmail:removeData(data)
            local info = EmailModel:getInfo(mail_type)
            if data.index <= #info.list then
                self:setSelectData(info.list[data.index])
            else
                self:setSelectData(info.list[data.index - 1])
            end
            self:refreshMailInfo()
            self:refreshEmailDetail()
        end
    end)
end

function P:evt_refreshEmailNum()
    self:refreshMailNum()
end

function P:evt_refreshEmailList(info)
	if info.mail_type == self._mail_type then
        local curSel = self._select_id
        self._select_id, self._select_data = nil, nil
        if curSel then
            for _, v in ipairs(info.list) do
                if v.id == curSel then
                    self._select_id = v.id
                    self._select_data = v
                    break
                end
            end
        end
        if not self._select_id then
            self:setSelectData(info.list[1], true)
        end
        self:refreshMailInfo()
        self.ListEmail:setDatas(info.list)
        self:refreshEmailDetail()
	end
end

return P