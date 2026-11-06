local P = class("TableChatLayer", UiDialog)

function P:onAwake()
    local Right = self:find("Right")
    local ChatTab = self:find("ChatTab", Right)
    self.EmojiToggle = self:find("EmojiToggle", ChatTab)
    self.FastToggle = self:find("FastToggle", ChatTab)
    self.AniEmojiToggle = self:find("AniEmojiToggle", ChatTab)
    self.ChatFoldButton = self:find("ChatFoldButton", Right)

    self.EmojiList = self:find("EmojiList", Right)
    self.FastList = self:find("FastList", Right)
    self.AniEmojiList = self:find("AniEmojiList", Right)
    self.ItemEmoji = self:find("Item1", self.EmojiList)
    self.ItemChat = self:find("Item1", self.FastList)
    self.ItemAniEmoji = self:find("ContentList/Item1", self.AniEmojiList)

    self.ItemEmoji:SetActive(false)
    self.ItemChat:SetActive(false)
    self.ItemAniEmoji:SetActive(false)

    self.AniEmojiIsOn = false
    self.cacheRoomId = ""
    self.cacheEmojiId = 0

    bee.addClick(self.ChatFoldButton, function()
        self:hideUI()
    end)

    bee.addValueChanged(self.EmojiToggle, function(isOn)
        if isOn then
            Game:playSound("ui_tab_switch_1")
            self:showEmoji()
            -- LocalStore:setIntegerForKey("table_chat_index", 0)
        end
    end)

    bee.addValueChanged(self.FastToggle, function(isOn)
        if isOn then
            Game:playSound("ui_tab_switch_1")
            self:showChat()
            -- LocalStore:setIntegerForKey("table_chat_index", 1)
        end
    end)

    bee.addValueChanged(self.AniEmojiToggle, function (isOn)
        self.AniEmojiIsOn = isOn
        if isOn then
            Game:playSound("ui_tab_switch_1")
            self:showAniEmoji()
            -- LocalStore:setIntegerForKey("table_chat_index", 2)
        end
    end)
end

function P:onShow()
    self._scheme = GameModel.data:getIngameScheme()
    bee.setCheck(self.AniEmojiToggle)
    self.AniEmojiIsOn = true
    self:showAniEmoji()
    -- local index = LocalStore:getIntegerForKey("table_chat_index", 0)
    -- if index == 0 then
    --     bee.setCheck(self.EmojiToggle)
    --     self:showEmoji()
    -- elseif index == 1 then
    --     bee.setCheck(self.FastToggle)
    --     self:showChat()
    -- elseif index == 2 then
    --     bee.setCheck(self.AniEmojiToggle)
    --     self.AniEmojiIsOn = true
    --     self:showAniEmoji()
    -- end
end

function P:getRoleId()
    local skin_id = GameModel.data:getIngameScheme().skin_id
    if tpl_character_skin[skin_id] then
        return tpl_character_skin[skin_id].role
    end
    local role = CharacterModel:getUsingRoleId()
    local player = GameModel.data and GameModel.data:getMyPlayerInfo()
    if player and player.role_id and player.role_id > 0 then
        role = player.role_id
    end
    return role
end

function P:showEmoji()
    self.EmojiList:SetActive(true)
    self.FastList:SetActive(false)
    self.AniEmojiList:SetActive(false)

    if not self.ListEmoji then
        self.ListEmoji = self:find("Viewport/Content", self.EmojiList)

        local role_id = self:getRoleId()
        local emojis = get_tpl_subKey(tpl_emoji_list, "role", role_id)
        local datas, r = {}, CharacterModel:getRole(role_id)
        for k, v in ipairs(emojis) do
            if not r or (v.unlock and r:getBondLevel() >= v.unlock) then
                table.insert(datas, v)
            end
        end

        if self._scheme.emojis then
            for _, v in ipairs(self._scheme.emojis) do
                local id = v
                local flag = true
                for _, vv in ipairs(datas) do
                    if vv.id == id then
                        flag = false
                        break
                    end
                end
                if flag then
                    table.insert(datas, tpl_emoji[id])
                end
            end
        end
        
        for _, data in ipairs(datas) do
            local item = CU.GameObject.Instantiate(self.ItemEmoji, self.ListEmoji.transform, false)
            item:SetActive(true)
            bee.setIcon(self:find("ingame_chat_emoji_01", item), data.emoji)
            bee.addClick(item, function()
                if not self:checkChatCD() then
                    return
                end
                Game:playSound("ui_button_confirm")
                Net:sendReq("pb.FaceREQ", {id = data.id})
                -- 上报任务进度：牌桌使用表情
                TaskModel:reportTask(TaskTargetId.TableChat, TaskTableChatType.Emoji)
                bee.logEvent("ingame-chat-emoji", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.id)
                self:hideUI(nil, true)
            end, true)
        end
    end
end

function P:showChat()
    self.EmojiList:SetActive(false)
    self.FastList:SetActive(true)
    self.AniEmojiList:SetActive(false)

    if not self.ListChat then
        self.ListChat = self:find("Viewport/Content", self.FastList)

        local chats = get_tpl_subKey(tpl_chat_list, "role", self:getRoleId())
        local datas, r = {}, CharacterModel:getCurRole()
        for k, v in ipairs(chats) do
            if v.kind == CHAT_VOICE_TYPE.Chat and (not r or r:getBondLevel() >= v.unlock) then
                if not v.language_type then
                    table.insert(datas, v)
                else
                    local isIn = false
                    for _, v1 in pairs(v.language_type) do
                        if LanguageManager:getLanguage() == v1 then
                            isIn = true
                            break
                        end
                    end
                    if isIn then
                        table.insert(datas, v)
                    end
                end
            end
        end
        
        for _, data in ipairs(datas) do
            local item = CU.GameObject.Instantiate(self.ItemChat, self.ListChat.transform, false)
            item:SetActive(true)
            bee.setText(self:find("Text", item), _T(data.text))
            bee.addClick(item, function()
                if not self:checkChatCD() then
                    return
                end
                Net:sendReq("pb.TextREQ", {id = data.id})
                -- 上报任务进度：牌桌使用快捷语
                TaskModel:reportTask(TaskTargetId.TableChat, TaskTableChatType.Text)
                bee.logEvent("ingame-chat-message", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.id)
                self:hideUI(nil, true)
            end, true)
        end
    end
end

function P:showAniEmoji()
    self.EmojiList:SetActive(false)
    self.FastList:SetActive(false)
    self.AniEmojiList:SetActive(true)
    bee.logEvent("ingame-emoji-new")

    local roomId = GameModel.data and GameModel.data:getRoomId() or 0
    local emojiData = LocalStore:getTableData("table_ani_emoji_data") or {}
    self.cacheRoomId = emojiData.roomId
    self.cacheEmojiId = emojiData.emojiId or 0
    if self.cacheRoomId ~= roomId then
        self.cacheRoomId = roomId
        self.cacheEmojiId = 0
    end

    if not self.ListAniEmoji then
        self.ListAniEmoji = self:find("ContentList", self.AniEmojiList)
        self.sltItemData = nil
        self.aniEmojiDataList = {}

        local KeepsButton = self:find("Top/common_checkbox_03_bg", self.AniEmojiList)
        local KeepsSign = self:find("Top/common_checkbox_01_fg", self.AniEmojiList)
        self.AniEmojiKeepsSend = LocalStore:getBoolForKey("table_ani_emoji_keeps", true)
        KeepsSign:SetActive(self.AniEmojiKeepsSend)
        bee.addClick(KeepsButton, function ()
            self.AniEmojiKeepsSend = not self.AniEmojiKeepsSend
            KeepsSign:SetActive(self.AniEmojiKeepsSend)
            LocalStore:setBoolForKey("table_ani_emoji_keeps", self.AniEmojiKeepsSend)
            bee.logEvent("ingame-emoji-setting", GameModel.data:getGameType(), GameModel.data:getRoomId(), self.AniEmojiKeepsSend and 1 or 2)
        end)

        local KeepsTipButton = self:find("Top/Title/TipButton", self.AniEmojiList)
        bee.addClick(KeepsTipButton, function ()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("CommonTextTipUD", {text = _T("LAB_GAME_EMOJI_07"), target = KeepsTipButton})
        end)

        local KeepsText = self:find("Top/Title/Text", self.AniEmojiList)
        local textWidth = KeepsText:GetComponent("Text").preferredWidth
        KeepsTipButton.transform.localPosition = bee.v3(textWidth + 25, 0, 0)

        local CurrencyIcon = self:find("Top/Currency/Icon", self.AniEmojiList)
        local CurrenctButton = self:find("Top/Currency", self.AniEmojiList)
        self.AniEmojiCurrencyText = self:find("Top/Currency/CountText", self.AniEmojiList)
        local ticketData = ItemModel:getItem(GPropId.TicketEmoji, true)
        -- bee.setText(self.AniEmojiCurrencyText, ticketData.num)
        bee.addClick(CurrencyIcon, function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("CommonItemTip", {data = ticketData, target = CurrencyIcon})
        end)
        bee.addClick(CurrenctButton, function ()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("BackpackDetail", {data = ticketData, hideBtn = true})
        end)

        self.AniEmojiRemainTip = self:find("Tip", self.AniEmojiList)

        self.AniEmojiItemList = UiListEx:create(self.ListAniEmoji)
        self.AniEmojiItemList:setCreateFunc(function()
            local item = CU.GameObject.Instantiate(self.ItemAniEmoji)
            item.gameObject:SetActive(true)
            return item
        end)
        self.AniEmojiItemList:setRefreshFunc(function(data, item)
            self:setEmojiItemShow(item, data)
        end)
        
        local rowCount = 3
        local rowPos = {}
        for i = 1, rowCount do
            table.insert(rowPos, ((i - 1) * 192) - 492)
        end
        self.AniEmojiItemList:setRowCount(rowCount)
        self.AniEmojiItemList:setRowPostions(rowPos)
        self.AniEmojiItemList:setWidth(192)

        self:refreshEmojiList()
    end

    local ticketData = ItemModel:getItem(GPropId.TicketEmoji, true)
    self:refreshCurrency(ticketData)
    self:refreshRemainTip()

end

--交互表情展示
function P:setEmojiItemShow(item, data)
    local emojiIcon = self:find("icon", item)
    local costValue = self:find("bottom/Value", item)
    local costIcon = self:find("bottom/CostIcon", item)
    local mask = self:find("ingame_emoji_img_mask", item)
    local lock = self:find("soccer_img_lock", item)
    -- local select = self:find("select", item)
    local freeText = self:find("bottom/Text", item)

    if self.sltItemData == nil then
        self.sltItemData = data
    end

    local free = EmojiModel.freeTimes > 0
    costValue:SetActive(not free)
    costIcon:SetActive(not free)
    freeText:SetActive(free)
    if not free then
        local costId = data.cfg.item[1]
        local costNeedCount = data.cfg.item[2]
        local costCfg = tpl_props[costId]
        bee.setIcon(costIcon, costCfg.icon)
        bee.setText(costValue, costNeedCount)

        local costRemainCount = ItemModel:getItemNumById(costId)
        local color = costRemainCount < costNeedCount and bee.colorHex("#C00036") or bee.colorHex("#DFDFDF")
        bee.setColor(costValue, color, "Text")
    end
    mask:SetActive(not data.unlock)
    lock:SetActive(not data.unlock)
    -- select:SetActive(self.sltItemData.cfg.id == data.cfg.id)
    bee.setIcon(emojiIcon, data.itemCfg.icon)
    -- emojiIcon:GetComponent("RectTransform").sizeDelta = bee.v2one * 140
    -- if self.sltItemData.cfg.id == data.cfg.id then
    --     EmojiModel:showEmojiInDisplay(emojiIcon, data.cfg, self.node)
    --     emojiIcon:GetComponent("RectTransform").sizeDelta = bee.v2(160, 96)
    -- else
    --     bee.setIcon(emojiIcon, data.itemCfg.icon)
    --     emojiIcon:GetComponent("RectTransform").sizeDelta = bee.v2one * 140
    -- end

    bee.addClick(item, function ()
        self.sltItemData = data
        local roomId = GameModel.data and GameModel.data:getRoomId() or 0
        local emojiData = {roomId = roomId, emojiId = data.cfg.id}
        LocalStore:saveTableData("table_ani_emoji_data", emojiData)

        if not data.unlock then
            UiManager:showToast(_T("LAB_CHAR_032"))
            -- self.AniEmojiItemList:setDatas(self.aniEmojiDataList)
        else
            if EmojiModel.freeTimes <= 0 then
                --道具不足
                local enough = EmojiModel:checkEnoughItem(data.cfg.id, "LAB_SHOP_COMMON_24")
                if not enough then
                    -- self.AniEmojiItemList:setDatas(self.aniEmojiDataList)
                    return
                end
            end

            self:hideUI()
            local order = GameModel.layer:getOrder()
            UiManager:showUI("IngameEmojiTipView", {keep = self.AniEmojiKeepsSend, itemId = data.itemCfg.id, emojiId = data.cfg.id, zOrder = order + 1})
            bee.logEvent("ingame-emoji-view", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.cfg.id)
        end
    end, true)
end

--刷新表情列表
function P:refreshEmojiList()
    self.aniEmojiDataList = {}
    
    local emojiPropList = get_tpl_subKey(tpl_props_list, "type", 401)
    for _,v in pairs(emojiPropList) do
        local emojiCfg = tpl_table_emoji[v.mapId]
        if emojiCfg then
            local itemData = ItemModel:getItem(v.id)
            local emojiData = {
                cfg = emojiCfg,
                itemCfg = v,
                unlock = itemData ~= nil,
                -- enough = true,
            }
            table.insert(self.aniEmojiDataList, emojiData)
        end
    end

    --排序
    table.sort(self.aniEmojiDataList, function (a, b)
        if a.unlock ~= b.unlock then
            return a.unlock
        end
        return a.cfg.sort < b.cfg.sort
    end)

    --设置默认选中
    local sltIndex = 1
    if self.cacheEmojiId == 0 then
        self.cacheEmojiId = self.aniEmojiDataList[1].cfg.id
        self.sltItemData = self.aniEmojiDataList[1]
        sltIndex = 1
    else
        sltIndex = 0
        for _,v in pairs(self.aniEmojiDataList) do
            sltIndex = sltIndex + 1
            if self.cacheEmojiId == v.cfg.id then
                self.sltItemData = v
                break
            end
        end
    end
    self.AniEmojiItemList:moveToYItem(sltIndex)

    self.AniEmojiItemList:setDatas(self.aniEmojiDataList)
end

--刷新表情道具数量
function P:refreshCurrency(ticketData)
    bee.setText(self.AniEmojiCurrencyText, ticketData.num)
end

--刷新剩余次数
function P:refreshRemainTip()
    bee.setText(self.AniEmojiRemainTip, _F("LAB_GAME_EMOJI_03", EmojiModel.freeTimes))
end

local _table_chat_cd = 0
function P:checkChatCD()
    local ct = bee.getServerTime()
    if math.abs(ct - _table_chat_cd) <= tpl_constdata.Quick_Chat_Cd_Time then
        local dt = math.ceil(math.abs(tpl_constdata.Quick_Chat_Cd_Time - math.abs(ct - _table_chat_cd)))
        if dt <= 0 then dt = 1 end
        UiManager:showToast(_F("LAB_GAME_007", dt))
        return false
    end
    _table_chat_cd = ct
    return true
end

function P:onPointerClick(e)
    self:hideUI()
end

--刷新道具
function P:evt_ItemChangeRSP()
    if not self.AniEmojiIsOn then
        return
    end

    self:refreshEmojiList()
    local ticketData = ItemModel:getItem(GPropId.TicketEmoji, true)
    self:refreshCurrency(ticketData)
end

function P:evt_serverTimeCrossDay()
    if not self.AniEmojiIsOn then
        return
    end

    EmojiModel:resetFreeTimes()
    self:refreshEmojiList()
    self:refreshRemainTip()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_gameBlur(flag, name)
    self:evt_uiBlur(flag, name)
end

return P