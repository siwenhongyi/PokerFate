local P = class("InformationAvatar", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)

    self.Empty = self:find("Empty", self.Center)
    self.SelectedInfo = self:find("SelectedInfo", self.Center)
    self.TextFrom = self:find("TextFrom", self.SelectedInfo)
    self.TextEquiped = self:find("TextEquiped", self.SelectedInfo)
    self.TextLimit = self:find("TextLimit", self.SelectedInfo)
    self.EquipButton = self:find("EquipButton", self.SelectedInfo)
    self.UnEquipButton = self:find("UnEquipButton", self.SelectedInfo)
    self.ClaimButton = self:find("ClaimButton", self.SelectedInfo)
    self.TextDec = self:find("DecList/Viewport/Content/TextDec", self.SelectedInfo)
    self.AvatarList = self:find("AvatarList", self.Center)
    self.AvatarItem1 = self:find("Item1", self.AvatarList)
    self.AvatarFrameList = self:find("AvatarFrameList", self.Center)
    self.FrameItem1 = self:find("Item1", self.AvatarFrameList)
    self.TitleList = self:find("TitleList", self.Center)
    self.TitleItem1 = self:find("Item1", self.TitleList)
    self.Avatar = self:find("Avatar", self.SelectedInfo)
    self.ImageFrame = self:find("ImageFrame", self.SelectedInfo)
    self.ImageTitle = self:find("ImageTitle", self.SelectedInfo)
    self.TextName = self:find("TextName", self.SelectedInfo)
    self.Filter = self:find("Filter", self.Center)
    self.CheckToggle = self:find("CheckToggle", self.Center)
    self.Tab = self:find("Tab", self.Center)
    self.Toggles = {
        self:find("Tab_01_Toggle", self.Tab),
        self:find("Tab_02_Toggle", self.Tab),
        self:find("Tab_03_Toggle", self.Tab),
    }

    self.AvatarItem1:SetActive(false)
    self.FrameItem1:SetActive(false)
    self.TitleItem1:SetActive(false)
    self.Filter:SetActive(false)

    self.PreviewButton = self:find("PreviewButton", self.SelectedInfo)

    bee.addClick(self:find("CloseButton", self.Center), function()
        ItemModel:requestRefreshItem()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        ItemModel:requestRefreshItem()
        self:hideUI()
    end)
    bee.addClick(self.EquipButton, function()
        if 1 == self._showIndex then
            Net:sendReq("pb.ChangeAvatarREQ", {item_id = self._curSelectItem.id})
        elseif 2 == self._showIndex then
            Net:sendReq("pb.ChangeFrameREQ", {item_id = self._curSelectItem.id})
        else
            Net:sendReq("pb.ChangeTitleREQ", {item_id = self._curSelectItem.id})
        end
    end)
    bee.addClick(self.UnEquipButton, function()
        if 1 == self._showIndex then
        elseif 2 == self._showIndex then
            Net:sendReq("pb.ChangeFrameREQ", {item_id = 0})
        else
            Net:sendReq("pb.ChangeTitleREQ", {item_id = 0})
        end
    end)
    bee.addClick(self.ClaimButton, function()
        Game:playSound("ui_button_confirm")
        local jump = self._curSelectItem.jump or self._curSelectItem.accesses[1]
        ItemModel:jumpView(jump, self._curSelectItem.id)
    end)
    bee.addClick(self.PreviewButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BackpackPreview", {data = self._curSelectItem})
    end)

    for k, v in ipairs(self.Toggles) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                if self:isShow() then
                    Game:playSound("ui_tab_switch_1")
                end
                self:showList(k)
                if 1 == k then
    	            bee.logEvent("profile-personalization-avatar")
                elseif 2 == k then
    	            bee.logEvent("profile-personalization-avatar-frame")
                elseif 3 == k then
                    bee.logEvent("profile-personalization-title")
                end
            end
        end)
    end

    bee.addValueChanged(self.CheckToggle, function(isOn)
        Game:playSound("ui_button_disabled")
        self:refreshAvatar()
        self:refreshFrame()
        self:refreshTitle()
        self:refreshEmpty()
    end)

    self._Lists = {}
end

function P:onShow()
    local index = self._params and self._params.index or 1
    bee.setCheck(self.Toggles[index], true)
    -- self:showList(index)

    -- 任务进度-查看玩家个人信息头像列表
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.InfoAvatarList)
    self._isShowed = true
end

function P:showList(index)
    self._showIndex = index
    self.PreviewButton:SetActive(false)
    if 1 == index then
        self.AvatarList:SetActive(true)
        self.AvatarFrameList:SetActive(false)
        self.TitleList:SetActive(false)
        self:showAvatarList()
        self:setCurSelectItem(self._selectAvatar)
    elseif 2 == index then
        self.AvatarList:SetActive(false)
        self.AvatarFrameList:SetActive(true)
        self.TitleList:SetActive(false)
        self:showFrameList()
        self:setCurSelectItem(self._selectFrame)
    else
        self.AvatarList:SetActive(false)
        self.AvatarFrameList:SetActive(false)
        self.TitleList:SetActive(true)
        self:showTitleList()
        self:setCurSelectItem(self._selectTitle)
    end
    self:refreshEmpty()
end

function P:sortDatas(datas)
    table.sort(datas, function(a, b)
        if a:isLocked() ~= b:isLocked() then
            return not a:isLocked()
        end
        return a.id < b.id
    end)
end

function P:refreshEmpty()
    if 1 == self._showIndex then
        self.Empty:SetActive(#self._dataAvatars == 0)
        self.SelectedInfo:SetActive(#self._dataAvatars > 0)
    elseif 2 == self._showIndex then
        self.Empty:SetActive(#self._dataFrames == 0)
        self.SelectedInfo:SetActive(#self._dataFrames > 0)
    else
        self.Empty:SetActive(#self._dataTitles == 0)
        self.SelectedInfo:SetActive(#self._dataTitles > 0)
    end
end

function P:showAvatarList()
    if not self.ListAvatar then
        self.ListAvatar = UiListEx:create(self.AvatarList)
        self.ListAvatar:setWidth(180)
        self.ListAvatar:setRowCount(4)
        self.ListAvatar:setCreateFunc(function(data)
            return CU.GameObject.Instantiate(self.AvatarItem1)
        end)
        self.ListAvatar:setRefreshFunc(function(data, item)
            self:refreshAvatarItem(data, item)
        end)

        self:refreshAvatar()
    end
end

function P:refreshAvatar()
    if self.ListAvatar then
        self._dataAvatars = self:getDatas(GPropKind.Avatar)
        self:sortDatas(self._dataAvatars)
        if not self._selectAvatar then
            for _, v in ipairs(self._dataAvatars) do
                if v.id == PlayerModel:getAvatar() then
                    self._selectAvatar = v
                    break
                end
            end
        end
        if not self._selectAvatar then
            self._selectAvatar = self._dataAvatars[1]
        end
        self.ListAvatar:setDatas(self._dataAvatars)
    end
end

function P:showFrameList()
    if not self.ListFrame then
        self.ListFrame = UiListEx:create(self.AvatarFrameList)
        self.ListFrame:setWidth(180)
        self.ListFrame:setRowCount(4)
        self.ListFrame:setCreateFunc(function(data)
            return CU.GameObject.Instantiate(self.FrameItem1)
        end)
        self.ListFrame:setRefreshFunc(function(data, item)
            self:refreshFrameItem(data, item)
        end)
        self:refreshFrame()
    end
end

function P:refreshFrame()
    if self.ListFrame then
        self._dataFrames = self:getDatas(GPropKind.FrameAvatar)
        self:sortDatas(self._dataFrames)
        if not self._selectFrame then
            for _, v in ipairs(self._dataFrames) do
                if v.id == PlayerModel:getFrame() then
                    self._selectFrame = v
                    break
                end
            end
        end
        if not self._selectFrame then
            self._selectFrame = self._dataFrames[1]
        end
        self.ListFrame:setDatas(self._dataFrames)
    end
end

function P:showTitleList()
    if not self.ListTitle then
        self.ListTitle = UiListEx:create(self.TitleList)
        self.ListTitle:setWidth(120)
        self.ListTitle:setRowCount(3)
        self.ListTitle:setCreateFunc(function(data)
            return CU.GameObject.Instantiate(self.TitleItem1)
        end)
        self.ListTitle:setRefreshFunc(function(data, item)
            self:refreshTitleItem(data, item)
        end)

        self:refreshTitle()
    end
end

function P:refreshTitle()
    if self.ListTitle then
        self._dataTitles = self:getDatas(GPropKind.Title)
        self:sortDatas(self._dataTitles)
        if not self._selectTitle then
            for _, v in ipairs(self._dataTitles) do
                if v.id == PlayerModel:getTitle() then
                    self._selectTitle = v
                    break
                end
            end
        end
        if not self._selectTitle then
            self._selectTitle = self._dataTitles[1]
        end
        self.ListTitle:setDatas(self._dataTitles)
    end
end

function P:getDatas(kind)
    local ct = bee.getServerTime()
    local flag = bee.isCheck(self.CheckToggle)
    local datas = {}
    local tbs = get_tpl_subKey(tpl_props_list, "type", kind)
    for _, v in ipairs(tbs) do
        local d = ItemModel:getItem(v.id, not flag)
        if d and d.bagShow == 1 and (not d.time_start or d.time_start <= ct or PlayerModel:isEventWhite()) then
            table.insert(datas, d)
        end
    end
    return datas
end

function P:refreshAvatarItem(data, item)
    if not item then return end
    self:find("Locked", item):SetActive(data:isLocked())
    self:find("ImageSelect", item):SetActive(self._selectAvatar == data)
    self:find("tag", item):SetActive(PlayerModel:getAvatar() == data.id)
    bee.setIcon(self:find("Avatar/Mask/ImageIcon", item), data.icon)
    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        if self._selectAvatar ~= data then
            local oldData = self._selectAvatar
            self._selectAvatar = data
            self:refreshAvatarItem(data, item)
            self:setCurSelectItem(data)
            if oldData then
                self:refreshAvatarItem(oldData, self.ListAvatar:getDataNode(oldData))
            end
        end
    end, true)
end

function P:refreshFrameItem(data, item)
    if not item then return end
    self:find("Locked", item):SetActive(data:isLocked())
    self:find("ImageSelect", item):SetActive(self._selectFrame == data)
    self:find("tag", item):SetActive(PlayerModel:getFrame() == data.id)
    bee.setIcon(self:find("ImageIcon", item), data.icon)
    bee.addClick(item, function()
        if self._selectFrame ~= data then
            local oldData = self._selectFrame
            self._selectFrame = data
            self:refreshFrameItem(data, item)
            self:setCurSelectItem(data)
            if oldData then
                self:refreshFrameItem(oldData, self.ListFrame:getDataNode(oldData))
            end
        end
    end, true)
end

function P:refreshTitleItem(data, item)
    if not item then return end
    self:find("Locked", item):SetActive(data:isLocked())
    self:find("ImageSelect", item):SetActive(self._selectTitle == data)
    self:find("tag", item):SetActive(PlayerModel:getTitle() == data.id)
    bee.setIcon(self:find("ImageIcon", item), data.icon, true)
    bee.addClick(item, function()
        if self._selectTitle ~= data then
            local oldData = self._selectTitle
            self._selectTitle = data
            self:refreshTitleItem(data, item)
            self:setCurSelectItem(data)
            if oldData then
                self:refreshTitleItem(oldData, self.ListTitle:getDataNode(oldData))
            end
        end
    end, true)
end

function P:setCurSelectItem(data)
    if not data then return end
    self._curSelectItem = data
    bee.setText(self.TextName, _T(data.name))
    bee.setText(self.TextDec, _T(data.des))
    self.PreviewButton:SetActive(data.preview == 1)

    self.Avatar:SetActive(self._showIndex == 1)
    self.ImageFrame:SetActive(self._showIndex == 2)
    self.ImageTitle:SetActive(self._showIndex == 3)
    local isInUse = false
    if 1 == self._showIndex then
        bee.setIcon(self:find("Mask/ImageIcon", self.Avatar), data.icon)
        isInUse = PlayerModel:getAvatar() == self._curSelectItem.id
    elseif 2 == self._showIndex then
        bee.setIcon(self.ImageFrame, data.icon)
        isInUse = PlayerModel:getFrame() == self._curSelectItem.id
    else
        bee.setIcon(self.ImageTitle, data.icon, true)
        isInUse = PlayerModel:getTitle() == self._curSelectItem.id
    end

    if self._countDownTag then
        scheduler:removeTag(self._countDownTag)
        self._countDownTag = nil
    end

    if isInUse then
        self.TextFrom:SetActive(false)
        self.TextEquiped:SetActive(self._showIndex == 1)
        self.TextLimit:SetActive(false)
        self.EquipButton:SetActive(false)
        self.UnEquipButton:SetActive(self._showIndex ~= 1)
        self.ClaimButton:SetActive(false)
    elseif data:isLocked() then
        self.TextEquiped:SetActive(false)
        self.EquipButton:SetActive(false)
        self.UnEquipButton:SetActive(false)
        local jump = data.accesses or data.jump
        local toId = data.id
        if data.type == GPropKind.Avatar then
            local jumpCfg = tpl_Jump_path[jump[1]]
            local skinCfg = tpl_character_skin[data.mapId]
            toId = jumpCfg.view == "GachaMain" and skinCfg.role or skinCfg.id
        end
        if ItemModel:isCanJump(jump, toId) then
            self.ClaimButton:SetActive(true)
            self.TextLimit:SetActive(false)
            self.TextFrom:SetActive(true)
            local d = tpl_Jump_path[data.accesses and data.accesses[1] or data.jump]
            if d then
                bee.setText(self.TextFrom, _T(d.name))
            end
        else
            self.ClaimButton:SetActive(false)
            self.TextFrom:SetActive(false)
            self.TextLimit:SetActive(true)
        end
    else
        self.TextFrom:SetActive(false)
        self.TextEquiped:SetActive(false)
        self.TextLimit:SetActive(false)
        self.EquipButton:SetActive(true)
        self.UnEquipButton:SetActive(false)
        self.ClaimButton:SetActive(false)
    end
    if (data.id == tpl_monthly_card[1].exc_frame[1] or data.id == tpl_monthly_card[1].exc_title[1]) and ShopModel:isMonthlyCard() then
        self.TextFrom:SetActive(true)
        local leftTime = ShopModel:getMonthlyCardLeftTime()
        bee.setText(self.TextFrom, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(leftTime)))
        self._countDownTag = self:schedule(1, function()
            leftTime = ShopModel:getMonthlyCardLeftTime()
            if leftTime > 0 then
                bee.setText(self.TextFrom, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(leftTime)))
            else
                bee.setText(self.TextFrom, _T("LAB_BACKPACK_DES_21"))
            end
        end)
    else
        local dt = data:getDeadLeftTime()
        if dt > 0 then
            self.TextFrom:SetActive(true)
            bee.setText(self.TextFrom, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(dt)))
            self._countDownTag = self:schedule(1, function()
                dt = data:getDeadLeftTime()
                if dt > 0 then
                    bee.setText(self.TextFrom, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(dt)))
                else
                    self:setCurSelectItem(data)
                end
            end)
        end
    end
end

function P:resetTagVisible(item, flag)
    if item then
        self:find("tag", item):SetActive(flag)
    end
end

function P:evt_ChangeAvatarRSP(msg)
    for _, v in ipairs(self._dataAvatars) do
        if v.id == PlayerModel:getAvatar() then
            self:resetTagVisible(self.ListAvatar:getDataNode(v), true)
            bee.emit(EventDef.evt_refreshAvatar)
        elseif v.id == PlayerModel._avatarOld then
            self:resetTagVisible(self.ListAvatar:getDataNode(v), false)
        end
    end
    self:setCurSelectItem(self._curSelectItem)
    UiManager:showToast(_T("LAB_INFO_030"))
end

function P:evt_ChangeFrameRSP(msg)
    for _, v in ipairs(self._dataFrames) do
        if v.id == PlayerModel:getFrame() then
            self:resetTagVisible(self.ListFrame:getDataNode(v), true)
        elseif v.id == PlayerModel._frameOld then
            self:resetTagVisible(self.ListFrame:getDataNode(v), false)
        end
    end
    self:setCurSelectItem(self._curSelectItem)
    UiManager:showToast(_T("LAB_INFO_031"))
end

function P:evt_ChangeTitleRSP(msg)
    for _, v in ipairs(self._dataTitles) do
        if v.id == PlayerModel:getTitle() then
            self:resetTagVisible(self.ListTitle:getDataNode(v), true)
        elseif v.id == PlayerModel._titleOld then
            self:resetTagVisible(self.ListTitle:getDataNode(v), false)
        end
    end
    self:setCurSelectItem(self._curSelectItem)
    UiManager:showToast(_T("LAB_INFO_032"))
end

function P:evt_ItemChangeRSP(msg)
    if self.ListAvatar then
        self._selectAvatar = ItemModel:getItem(self._selectAvatar.id, true)
        self:refreshAvatar()
    end
    if self.ListFrame then
        self._selectFrame = ItemModel:getItem(self._selectFrame.id, true)
        self:refreshFrame()
    end
    if self.ListTitle then
        self._selectTitle = ItemModel:getItem(self._selectTitle.id, true)
        self:refreshTitle()
    end
    local datas = 1 == self._showIndex and self._dataAvatars or (2 == self._showIndex and self._dataFrames or self._dataTitles)
    for _, v in ipairs(datas) do
        if v.id == self._curSelectItem.id then
            self:setCurSelectItem(v)
            break
        end
    end
end

