local P = class("GachaMain", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.LeftBottom = self:find("LeftBottom", self.AnimRoot)
    self.Left = self:find("Left", self.AnimRoot)
    self.Right = self:find("Right", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.Center = self:find("Center", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)

    self.LoadingMask = self:find("LoadingMask")
    self.LoadingBackButton = self:find("LoadingBackButton", self.LoadingMask)

    local Currency = self:find("Currency", self.RightTop)
    self.ExchangeCoinIcon = self:find("ExchangeCoin/ExchangeCoinIcon", Currency)
    self.ExchangeCoinText = self:find("ExchangeCoin/ExchangeCoinText", Currency)
    self.DrawCoin = self:find("DrawCoin", Currency)
    self.DrawCoinIcon = self:find("DrawCoinIcon", self.DrawCoin)
    self.DrawCoinText = self:find("DrawCoinText", self.DrawCoin)
    self.DrawTicket = self:find("DrawTicket", Currency)
    self.DrawTicketIcon = self:find("DrawTicketIcon", self.DrawTicket)
    self.DrawTicketText = self:find("DrawTicketText", self.DrawTicket)

    self.Up = self:find("Up", self.RightTop)
    self.Up:SetActive(false)
    self.UpTag = self:find("UpTag", self.Up)
    self.UpNameText = self:find("UpNameText", self.Up)
    self.UpTimeText = self:find("UpTimeText", self.Up)
    
    self.SkipToggle = self:find("SkipToggle", self.RightBottom)

    self.RecruitScrollView = self:find("RecruitList", self.Left)
    self.ItemNormal = self:find("ItemNormal", self.RecruitScrollView)
    self.ItemNormal:SetActive(false)

    self.Recruit1Button = self:find("Recruit1Button", self.RightBottom)
    self.Draw1Currency = self:find("Draw1Currency", self.Recruit1Button)
    self.Recruit10Button = self:find("Recruit10Button", self.RightBottom)
    self.Draw10Currency = self:find("Draw10Currency", self.Recruit10Button)
    self.Draw10Coin = self:find("Draw10Coin", self.Draw10Currency)
    self.Draw10Ticket = self:find("Draw10Ticket", self.Draw10Currency)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self.LoadingBackButton, function()
        self:hideUI()
    end)
    
    bee.addClick(self:find("SettingButton", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Setting")
        bee.logEvent("recruit-setting")
    end)
    bee.addClick(self.DrawCoin, function()
        Game:playSound("ui_button_confirm")
        self:onClickAddButton(tpl_constdata.CharacterDropCoin[1])
        bee.logEvent("recruit-add-roulettecrystal")
    end)
    bee.addClick(self.DrawTicket, function()
        Game:playSound("ui_button_confirm")
        self:onClickAddButton(tpl_constdata.CharacterDropTicket[1])
        bee.logEvent("recruit-add-bondchip")
    end)
    bee.addClick(self.ExchangeCoinIcon, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(tpl_constdata.CharacterDropRewards, true), target = self.ExchangeCoinIcon})
    end)
    bee.addClick(self.DrawCoinIcon, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(tpl_constdata.CharacterDropCoin[1], true), target = self.DrawCoinIcon})
    end)
    bee.addClick(self.DrawTicketIcon, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(tpl_constdata.CharacterDropTicket[1], true), target = self.DrawTicketIcon})
    end)

    bee.addClick(self.Recruit1Button, function()
        Game:playSound("ui_button_confirm")
        self:onClickRecruitOne()
    end)
    bee.addClick(self.Recruit10Button, function()
        Game:playSound("ui_button_confirm")
        self:onClickRecruitTen()
    end)

    bee.addClick(self:find("ContentButton", self.LeftBottom), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("GachaMainDetail", {id = self._selectedCardPool})
        bee.logEvent("recruit-overview")
    end)

    bee.addClick(self:find("ShopButton", self.LeftBottom), function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpView(tpl_constdata.CharacterDropExchange)
        bee.logEvent("recruit-exchange-shop")
    end)

    bee.addValueChanged(self.SkipToggle, function(isOn)
        Game:playSound("ui_button_disabled")
        GachaModel:setSkipAnimFlag(isOn)
        bee.logEvent("recruit-skip-animation", isOn and 1 or 0)
    end)

    self._timeTags = {}

    -- 任务-查看抽卡界面
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Gacha)

    if GachaModel:getSkipAnimFlag() then
        bee.setCheck(self.SkipToggle)
    else
        bee.setUncheck(self.SkipToggle)
    end
end

function P:evt_lan_mod()
    self:setRecruitList()
    self:setCardPoolShow()
    self:setCurrencyShow()
end

function P:onStart()
    if self._params and self._params.jump then
        if self._params.jumpId then
            self._selectedCardPool = GachaModel:getContainCardPoolId(self._params.jumpId)
        elseif self._params.jump.select then
            self._selectedCardPool = self._params.jump.select
        end
    end

    bee.setIconInAtlas(self.ExchangeCoinIcon, tpl_props[tpl_constdata.CharacterDropRewards].icon)
    bee.setIconInAtlas(self.DrawCoinIcon, tpl_props[tpl_constdata.CharacterDropCoin[1]].icon)
    bee.setIconInAtlas(self.DrawTicketIcon, tpl_props[tpl_constdata.CharacterDropTicket[1]].icon)

    self.LoadingMask:SetActive(true)
    self.AnimRoot:SetActive(false)
    self._waitInit = true
    
    GachaModel:initGachaPoolList(true)
end

function P:evt_ItemChangeRSP(msg)
    self:setCurrencyShow()
end

function P:evt_gachaUpdate(params)
    local isMove = false
    if self._waitInit then
        self._waitInit = false
        self:initList()
        self:setCurrencyShow()
        self.LoadingMask:SetActive(false)
        self.AnimRoot:SetActive(true)
        isMove = true
    end

    self:setRecruitList(isMove)
    self:setCardPoolShow()

    if params and params.isNew then
        self.LoadingMask:SetActive(true)
        self.AnimRoot:SetActive(false)
        self:once(1.5, function()
            self.LoadingMask:SetActive(false)
            self.AnimRoot:SetActive(true)
        end)
    end
end

function P:initList()
    self.RecruitList = UiListEx:create(self.RecruitScrollView)
    self.RecruitList:setWidth(170)
    self.RecruitList:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.ItemNormal)
    end)
    self.RecruitList:setRefreshFunc(function(data, item)
        self:refreshBanner(item, data)
    end)
end

function P:refreshBanner(item, data)
    local OffItem = self:find("off", item)
    local OnItem = self:find("on", item)

    if data.pool_id == self._selectedCardPool then
        OffItem:SetActive(false)
        OnItem:SetActive(true)
        self:setBannerItemShow(OnItem, data, true)
    else
        OffItem:SetActive(true)
        OnItem:SetActive(false)
        self:setBannerItemShow(OffItem, data)
    end

    bee.removeAllClick(item)
    bee.addClick(item, function()
        Game:playSound("ui_tab_switch_1")
        if data.pool_id == self._selectedCardPool then
            return
        end

        self._selectedCardPool = data.pool_id
        self:setRecruitList()

        self:setCardPoolShow()

        bee.logEvent("recruit-card-pool", data.pool_id)
    end)
end

function P:setBannerItemShow(item, data, isOn)
    local ItemIcon = self:find("ItemIcon", item)
    local NameText = self:find("NameText", item)
    local TimeBg = self:find("TimeBg", item)
    local TimeText = self:find("TimeBg/TimeText", item)

    local cfg = tpl_card_pool[data.pool_id]
    bee.setText(NameText, _T(cfg.name))
    bee.setIcon(ItemIcon, cfg.image .. (isOn and "_on" or "_off"), "Gacha", true)

    if self._timeTags[item] then
        scheduler:removeTag(self._timeTags[item])
    end

    if data.end_ts and data.end_ts > 0 then
        TimeBg:SetActive(true)

        local leftTime = data.end_ts - bee.getServerTime()
        if leftTime > 0 then
            bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
            self._timeTags[item] = bee.schedule(1, function()
                leftTime = leftTime - 1
                if leftTime > 0 then
                    bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
                else
                    bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
                end
            end, item)
        else
            bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
        end
    else
        TimeBg:SetActive(false)
    end
end

function P:setRecruitList(isMove)
    -- self.RecruitList:clear()
    self.RecruitList:setDatas({})
    local list = GachaModel:getCardPoolList()
    if not list or not next(list) then
        self.RecruitList:setDatas({})
        self._selectedCardPool = nil
        return
    end

    local index = 1
    if not self._selectedCardPool then
        self._selectedCardPool = list[1].pool_id
    else
        local isIn = false
        for k,v in pairs(list) do
            if v.pool_id == self._selectedCardPool then
                index = k
                isIn = true
                break
            end
        end
        if not isIn then
            self._selectedCardPool = list[1].pool_id
        end
    end

    self.RecruitList:setDatas(list)
    if isMove then
        self.RecruitList:moveToYItem(index)
    end
end

-- 卡池信息
function P:setCardPoolShow()
    if self.upScheduleTag then
        scheduler:removeTag(self.upScheduleTag)
        self.upScheduleTag = nil
    end

    if self._gachaCenterItem then
        ObjectCache:putItem(self._gachaCenterItem)
        self._gachaCenterItem = nil
    end

    if not self._selectedCardPool then
        return
    end

    local cfg = tpl_card_pool[self._selectedCardPool]
    if not cfg then
        return
    end
    
    local centerItem = ObjectCache:getItemWithName("views/Gacha/" .. cfg.prefab)
    if not centerItem then
        return
    end

    centerItem.transform:SetParent(self.Center.transform)
    centerItem.transform.localPosition = bee.v3(0, 0, 0)
    centerItem.transform.localScale = bee.v3(1, 1, 1)
    self._gachaCenterItem = centerItem
  
    local characterCount = #cfg.character
    -- 角色信息
    for i, v in ipairs(cfg.character) do
        self:setRole(self:find("Character/Role" .. i, centerItem), v, cfg)
        self:setNameCard(self:find("NameCard" .. i, centerItem), v)
    end

    local titleList = {}
    titleList["tw"] = self:find("Title/TitleTw", centerItem)
    titleList["en"] = self:find("Title/TitleEn", centerItem)
    titleList["jp"] = self:find("Title/TitleJp", centerItem)
    titleList["zh"] = self:find("Title/TitleZh", centerItem)
    local showTitle
    local curLan = LanguageManager:getLanguage()
    for k, v in pairs(titleList) do
        if k == curLan then
            v:SetActive(true)
            showTitle = v
        else
            v:SetActive(false)
        end
    end
    local TipsText = self:find("TipsBg/TipsText", showTitle)
    bee.setText(TipsText, _T(cfg.des))

    if cfg.up then
        self.Up:SetActive(true)

        bee.setIconInAtlas(self.UpTag, cfg.up)
        local upRole = tpl_character[cfg.up_character[1]]
        bee.setText(self.UpNameText, _T(upRole.name))

        local endTime = GachaModel:getCardPoolEndTime(self._selectedCardPool)
        if endTime > 0 then
            self.UpTimeText:SetActive(true)

            local leftTime = endTime - bee.getServerTime()
            if leftTime > 0 then
                bee.setText(self.UpTimeText, _F("LAB_GACHA_028", ShopModel:getShopTimeText(leftTime)))
                self.upScheduleTag = self:schedule(1, function()
                    leftTime = leftTime - 1
                    if leftTime > 0 then
                        bee.setText(self.UpTimeText, _F("LAB_GACHA_028", ShopModel:getShopTimeText(leftTime)))
                    else
                        bee.setText(self.UpTimeText, _T("LAB_BACKPACK_DES_21"))
                    end
                end)
            else
                bee.setText(self.UpTimeText, _T("LAB_BACKPACK_DES_21"))
            end
        else
            self.UpTimeText:SetActive(false)
        end
    else
        self.Up:SetActive(false)
    end

    if self._selectedCardPool == 10005 then
        self:find("Title/gacha_rainyleisure_title_bg_word_02", centerItem):SetActive(curLan ~= "en")
        self:find("Title/gacha_rainyleisure_title_bg_word_01", centerItem):SetActive(curLan ~= "en")
    elseif self._selectedCardPool == 20012 then
        self:find("bg_gacha_nightflame_bird", centerItem):SetActive(false)
    end
end

function P:setRole(item, id, cfg)
    local showSkin = get_tpl_subKey(tpl_character_skin_list, "role", id)[1]
    local RoleImg = self:find("RoleImg", item)
    if RoleImg then
        bee.setIcon(RoleImg, showSkin.image, true)

        if cfg and cfg.up then
            if cfg.up_character_offset then
                RoleImg.transform.localPosition = bee.v3(cfg.up_character_offset[1], cfg.up_character_offset[2], 0)
                if cfg.up_character_offset[3] then
                    RoleImg.transform.localScale = bee.v3(cfg.up_character_offset[3], cfg.up_character_offset[3], 1)
                end
            else
                RoleImg.transform.localPosition = bee.v3(0, 0, 0)
                RoleImg.transform.localScale = bee.v3(1, 1, 1)
            end
        end
    end
end

function P:setNameCard(item, id)
    if not item then
        return
    end

    local CVNameText = self:find("CVNameText", item)
    local NameText = self:find("NameText", item)
    local CharacterIcon = self:find("CharacterIcon", item)
    local ViewButton = self:find("ViewButton", item)

    local characterCfg = tpl_character[id]

    bee.setText(CVNameText, "CV: " .. _T(characterCfg.cv))
    bee.setText(NameText, _T(characterCfg.name))
    bee.setIconInAtlas(CharacterIcon, characterCfg.icon, true)

    bee.removeAllClick(item)
    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterMainProfile", {data = CharacterModel:getRoleData(id)})
        bee.logEvent("recruit-card-pool-view", self._selectedCardPool, id)
    end)
end

function P:setCurrencyShow()
    local drawCoin = tpl_constdata.CharacterDropCoin
    local drawCoinTen = tpl_constdata.CharacterDropCoinTen
    local drawTicket = tpl_constdata.CharacterDropTicket

    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

    -- 货币栏显示
    bee.setTextGold(self.ExchangeCoinText, _N(ItemModel:getItemNumById(GPropId.ExchangeCoin)))
    bee.setTextGold(self.DrawCoinText, _N(curCoinCount))
    bee.setTextGold(self.DrawTicketText, _N(curTicketCount))

    -- 单抽数量显示
    if curTicketCount >= 1 then
        -- 足够芯片
        bee.setIconInAtlas(self:find("DrawIcon", self.Draw1Currency), tpl_props[GPropId.DrawTicket].icon)
        bee.setText(self:find("DrawText", self.Draw1Currency), "x1")
        self:find("DrawText", self.Draw1Currency):SetActive(true)
        self:find("DrawRedText", self.Draw1Currency):SetActive(false)
    else
        if curCoinCount >= tonumber(drawCoin[2]) then
            -- 足够水晶
            bee.setIconInAtlas(self:find("DrawIcon", self.Draw1Currency), tpl_props[GPropId.DrawCoin].icon)
            bee.setText(self:find("DrawText", self.Draw1Currency), "x" .. drawCoin[2])
            self:find("DrawText", self.Draw1Currency):SetActive(true)
            self:find("DrawRedText", self.Draw1Currency):SetActive(false)
        else
            -- 都不满足
            bee.setIconInAtlas(self:find("DrawIcon", self.Draw1Currency), tpl_props[GPropId.DrawTicket].icon)
            bee.setText(self:find("DrawRedText", self.Draw1Currency), "x1")
            self:find("DrawText", self.Draw1Currency):SetActive(false)
            self:find("DrawRedText", self.Draw1Currency):SetActive(true)
        end
    end

    -- 十连数量显示
    bee.setIconInAtlas(self:find("DrawIcon", self.Draw10Coin), tpl_props[GPropId.DrawCoin].icon)
    bee.setIconInAtlas(self:find("DrawIcon", self.Draw10Ticket), tpl_props[GPropId.DrawTicket].icon)
    if curTicketCount >= 10 then
        -- 芯片足够10抽
        self.Draw10Coin:SetActive(false)
        self.Draw10Ticket:SetActive(true)
        bee.setText(self:find("DrawText", self.Draw10Ticket), "x10")
        self:find("DrawText", self.Draw10Ticket):SetActive(true)
        self:find("DrawRedText", self.Draw10Ticket):SetActive(false)
    else
        if curTicketCount >= 1 then
            -- 还有芯片时优先判断是否可靠水晶补齐
            local lackTicket = 10 - curTicketCount
            local lackCount = (drawCoinTen[2] / 10) * lackTicket
            if lackCount <= curCoinCount then
                -- 足够水晶补齐
                self.Draw10Coin:SetActive(true)
                self.Draw10Ticket:SetActive(true)
                bee.setText(self:find("DrawText", self.Draw10Coin), "x" .. lackCount)
                bee.setText(self:find("DrawText", self.Draw10Ticket), "x" .. curTicketCount)
                self:find("DrawText", self.Draw10Ticket):SetActive(true)
                self:find("DrawRedText", self.Draw10Ticket):SetActive(false)
            else
                -- 不够水晶补齐
                self.Draw10Coin:SetActive(false)
                self.Draw10Ticket:SetActive(true)
                bee.setText(self:find("DrawRedText", self.Draw10Ticket), "x10")
                self:find("DrawText", self.Draw10Ticket):SetActive(false)
                self:find("DrawRedText", self.Draw10Ticket):SetActive(true)
            end
        elseif curCoinCount >= tonumber(drawCoinTen[2]) then
            -- 水晶足够10抽
            self.Draw10Coin:SetActive(true)
            self.Draw10Ticket:SetActive(false)
            bee.setText(self:find("DrawText", self.Draw10Coin), "x" .. drawCoinTen[2])
        else
            self.Draw10Coin:SetActive(false)
            self.Draw10Ticket:SetActive(true)
            bee.setText(self:find("DrawRedText", self.Draw10Ticket), "x10")
            self:find("DrawText", self.Draw10Ticket):SetActive(false)
            self:find("DrawRedText", self.Draw10Ticket):SetActive(true)
        end
    end
end

function P:onClickAddButton(id)
    ItemModel:jumpView(tpl_props[id].accesses[1])
end

function P:onClickRecruitOne()
    local drawCoin = tpl_constdata.CharacterDropCoin
    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

    -- 单抽消耗
    local costList = {}
    if curTicketCount >= 1 then
        table.insert(costList, {id = GPropId.DrawTicket, count = 1})
    elseif curCoinCount >= tonumber(drawCoin[2]) then
        table.insert(costList, {id = GPropId.DrawCoin, count = drawCoin[2]})
    end

    -- 数量不足跳转获取
    if not next(costList) then
        -- 跳转提示
        local params = {}
        local propCfg = tpl_props[GPropId.DrawTicket]
        params.text = _F("LAB_GACHA_023", _T(propCfg.name))
        params.onSure = function()
            ItemModel:jumpView(propCfg.accesses[1])
        end
        UiManager:showTip(params)
        return
    end

    if bee.checkCd("DrawCard", 2) then
        Game:playGachaMusic()
        GachaModel:recruitOne(self._selectedCardPool, costList)
    end
end

function P:onClickRecruitTen()
    local drawCoinTen = tpl_constdata.CharacterDropCoinTen
    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

    local costList = {}
    if curTicketCount >= 10 then
        -- 芯片足够10抽
        table.insert(costList, {id = GPropId.DrawTicket, count = 10})
    else
        if curTicketCount >= 1 then
            local lackTicket = 10 - curTicketCount
            local lackCount = (drawCoinTen[2] / 10) * lackTicket
            if lackCount <= curCoinCount then
                -- 足够水晶补齐
                table.insert(costList, {id = GPropId.DrawTicket, count = curTicketCount})
                table.insert(costList, {id = GPropId.DrawCoin, count = lackCount})
            end
        elseif curCoinCount >= tonumber(drawCoinTen[2]) then
            table.insert(costList, {id = GPropId.DrawCoin, count = drawCoinTen[2]})
        end
    end

    -- 数量不足跳转获取
    if not next(costList) then
        -- 跳转提示
        local params = {}
        local propCfg = tpl_props[GPropId.DrawTicket]
        params.text = _F("LAB_GACHA_023", _T(propCfg.name))
        params.onSure = function()
            ItemModel:jumpView(propCfg.accesses[1])
        end
        UiManager:showTip(params)
        return
    end

    if bee.checkCd("DrawCard", 2) then
        Game:playGachaMusic()
        GachaModel:recruitTen(self._selectedCardPool, costList)
    end
end

return P