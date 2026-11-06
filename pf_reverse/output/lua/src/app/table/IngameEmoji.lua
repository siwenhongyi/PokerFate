local P = class("IngameEmoji", Object)

function P:onAwake()
    self.Currency = self:find("Currency")
    self.ContentList = self:find("ContentList")
    self.Item1 = self:find("Item1", self.ContentList)
    self.Item1:SetActive(false)
    self.Tip = self:find("Tip")
    self.ConsumeButton = self:find("ConsumeButton")

    self.playerUid = 0

    bee.addClick(self.ConsumeButton, function ()
        Game:playSound("ui_button_confirm")
        self:sendEmojiEvent()
    end)

    self.itemList = UiListEx:create(self.ContentList)
	self.itemList:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.Item1)
		item.gameObject:SetActive(true)
		return item
	end)
	self.itemList:setRefreshFunc(function(data, item)
		self:setEmojiItemShow(item, data)
	end)
    local rowCount = 5
	local rowPos = {}
	for i = 1, rowCount do
		table.insert(rowPos, ((i - 1) * 200) - 393)
	end
    self.itemList:setRowCount(rowCount)
	self.itemList:setRowPostions(rowPos)
    self.itemList:setWidth(220)
end

function P:setPlayerUid(uid)
    self.playerUid = uid
end

function P:onStart()
    self.emojiPropList = get_tpl_subKey(tpl_props_list, "type", 401)
    bee.logEvent("ingame-emoji", GameModel.data:getGameType(), GameModel.data:getRoomId(), self.playerUid == PlayerModel:getUid() and 1 or 2)

    self:initCurrency()
    self:refreshEmojiList()
    self:refreshRemainTip()
end

function P:initCurrency()
    local iconButton = self:find("Icon", self.Currency)
    local ticketData = ItemModel:getItem(GPropId.TicketEmoji, true)
    bee.addClick(iconButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ticketData, target = iconButton})
    end, true)
    bee.addClick(self.Currency, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BackpackDetail", {data = ticketData, hideBtn = true})
    end, true)
    self:refreshCurrency(ticketData)
end

--发送表情
function P:sendEmojiEvent()
    local sendable = false

    --未解锁
    if not self.sltItemData.unlock then
        sendable = false
        UiManager:showToast(_T("LAB_CHAR_032"))
    else
        if EmojiModel.freeTimes <= 0 then
            --道具不足
            local costId = self.sltItemData.cfg.item[1]
            local costNeedCount = self.sltItemData.cfg.item[2]
            local costRemainCount = ItemModel:getItemNumById(costId)
            if costRemainCount < costNeedCount then
                UiManager:showToast(_F("LAB_GAME_EMOJI_04", _T(tpl_props[costId].name)))
                sendable = false
            else
                sendable = true
            end
        else
            sendable = true
        end
    end

    if sendable then
        EmojiModel:SendEmoji(self.sltItemData.cfg.id, self.playerUid)
    else
        bee.logEvent("ingame-emoji-send", GameModel.data:getGameType(), GameModel.data:getRoomId(), self.playerUid, 2)
    end
end

--刷新剩余次数
function P:refreshRemainTip()
    bee.setText(self.Tip, _F("LAB_GAME_EMOJI_03", EmojiModel.freeTimes))
end
--刷新表情列表
function P:refreshEmojiList()
    self.emojiList = {}
    
    for _,v in pairs(self.emojiPropList) do
        local emojiCfg = tpl_table_emoji[v.mapId]
        if emojiCfg then
            local itemData = ItemModel:getItem(v.id)
            local emojiData = {
                cfg = emojiCfg,
                itemCfg = v,
                unlock = itemData ~= nil,
                -- enough = true,
            }
            table.insert(self.emojiList, emojiData)
        end
    end

    --排序
    table.sort(self.emojiList, function (a, b)
        if a.unlock ~= b.unlock then
            return a.unlock
        end
        return a.cfg.sort < b.cfg.sort
    end)
    self.itemList:setDatas(self.emojiList)
end

function P:setEmojiItemShow(item, data)
    local emojiIcon = self:find("EmojiIcon", item)
    local costValue = self:find("Value", item)
    local costIcon = self:find("CostIcon", item)
    local mask = self:find("ingame_emoji_img_mask", item)
    local lock = self:find("soccer_img_lock", item)
    local select = self:find("select", item)
    local freeText = self:find("Text", item)

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
        local color = costRemainCount < costNeedCount and bee.colorHex("#C00036") or bee.colorHex("#373737")
        bee.setColor(costValue, color, "Text")
    end
    mask:SetActive(not data.unlock)
    lock:SetActive(not data.unlock)
    select:SetActive(self.sltItemData.cfg.id == data.cfg.id)
    if self.sltItemData.cfg.id == data.cfg.id then
        EmojiModel:showEmojiInDisplay(emojiIcon, data.cfg, self.node)
        emojiIcon:GetComponent("RectTransform").sizeDelta = bee.v2(170, 102)
    else
        bee.setIcon(emojiIcon, data.itemCfg.icon)
        emojiIcon:GetComponent("RectTransform").sizeDelta = bee.v2one * 150
    end

    bee.addClick(item, function ()
        if self.sltItemData.cfg.id ~= data.cfg.id then
            self.sltItemData = data
            self.itemList:setDatas(self.emojiList)
            bee.logEvent("ingame-emoji-view", GameModel.data:getGameType(), GameModel.data:getRoomId(), data.cfg.id)
        end
    end, true)
end

function P:refreshCurrency(ticketData)
    bee.setText(self:find("CountText", self.Currency), ticketData.num)
end

function P:evt_ItemChangeRSP()
    self:refreshEmojiList()
    local ticketData = ItemModel:getItem(GPropId.TicketEmoji, true)
    self:refreshCurrency(ticketData)
end

function P:evt_serverTimeCrossDay()
    EmojiModel:resetFreeTimes()
    self:refreshEmojiList()
    self:refreshRemainTip()
end

return P