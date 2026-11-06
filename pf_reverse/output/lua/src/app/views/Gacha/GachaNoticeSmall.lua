local P = class("GachaNoticeSmall", UiDialog)

function P:onAwake()
	local Notice = self:find("AnimRoot/Center/Notice")

    self.DrawCurrency = self:find("DrawCurrency", Notice)
    self.DrawCoin = self:find("DrawCoin", self.DrawCurrency)
    self.DrawTicket = self:find("DrawTicket", self.DrawCurrency)
    self.ToggleCheck = self:find("BgNoTip/ToggleCheck", Notice)
    
    self.ConfirmButton = self:find("ConfirmButton", Notice)
    self.CancelButton = self:find("CancelButton", Notice)
    self.CloseButton = self:find("CloseButton", Notice)

    bee.addClick(self.CloseButton, function()
    	self:saveCheckToggle()
    	self:hideUI()
	end)
	bee.addClick(self.CancelButton, function()
		self:saveCheckToggle()
		self:hideUI()
        bee.logEvent("recruit-return-confirm", self._params.poolId, self._params.drawCount, 2)
	end)
	bee.addClick(self.ConfirmButton, function()
		local curDrawCount = self._params.drawCount or 1
		if curDrawCount == 10 then
			self:onClickRecruitTen()
		else
			self:onClickRecruitOne()
		end
	end)
    bee.addValueChanged(self.ToggleCheck, function(isOn)
        if isOn then
            bee.logEvent("recruit-return-confirm-ban", self._params.poolId, self._params.drawCount)
        end
    end)
end

function P:onStart()
	local curDrawCount = self._params.drawCount or 1

    local drawCoin = tpl_constdata.CharacterDropCoin
    local drawCoinTen = tpl_constdata.CharacterDropCoinTen
    local drawTicket = tpl_constdata.CharacterDropTicket

    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

    if curDrawCount == 1 then
	    -- 单抽数量显示
	    if curTicketCount >= 1 then
	    	-- 足够芯片
	    	self.DrawTicket:SetActive(true)
	    	self.DrawCoin:SetActive(false)
	        PropItem:create(self.DrawTicket, {item_id = GPropId.DrawTicket, num = 1}):bindTips()
	    else
	        if curCoinCount >= tonumber(drawCoin[2]) then
	        	-- 足够彩晶
		    	self.DrawTicket:SetActive(false)
		    	self.DrawCoin:SetActive(true)
		        PropItem:create(self.DrawCoin, {item_id = GPropId.DrawCoin, num = drawCoin[2]}):bindTips()
	        end
	    end
	else
		-- 十连数量显示
	    if curTicketCount >= 10 then
	        -- 芯片足够10抽
	    	self.DrawTicket:SetActive(true)
	    	self.DrawCoin:SetActive(false)
	        PropItem:create(self.DrawTicket, {item_id = GPropId.DrawTicket, num = 10}):bindTips()
	    else
	    	local lackTicket = 10 - curTicketCount
	        local lackCount = (drawCoinTen[2] / 10) * lackTicket
	        if curTicketCount >= 1 and lackCount <= curCoinCount then
                -- 足够水晶补齐
                self.DrawTicket:SetActive(true)
                self.DrawCoin:SetActive(true)
                PropItem:create(self.DrawTicket, {item_id = GPropId.DrawTicket, num = curTicketCount}):bindTips()
                PropItem:create(self.DrawCoin, {item_id = GPropId.DrawCoin, num = lackCount}):bindTips()
	        elseif curCoinCount >= tonumber(drawCoinTen[2]) then
				-- 足够彩晶
		    	self.DrawTicket:SetActive(false)
		    	self.DrawCoin:SetActive(true)
		        PropItem:create(self.DrawCoin, {item_id = GPropId.DrawCoin, num = drawCoinTen[2]}):bindTips()
	        end
	    end
	end
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
        bee.logEvent("recruit-click", self._params.poolId, 0)
        return
    end
    
    if bee.checkCd("DrawCard", 2) then
        Game:playGachaMusic()
        bee.logEvent("recruit-return-confirm", self._params.poolId, 1, 1)
        GachaModel:recruitOne(self._params.poolId, costList)
        bee.emit("evt_gachaStart")
        self:hideUI()
        if self._params and self._params.confirmCb then
            self._params.confirmCb()
        end
    end
    self:saveCheckToggle()
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
        bee.logEvent("recruit-click-10", self._params.poolId, 0)
        return
    end

    if bee.checkCd("DrawCard", 2) then
        Game:playGachaMusic()
        bee.logEvent("recruit-return-confirm", self._params.poolId, 10, 1)
        GachaModel:recruitTen(self._params.poolId, costList)
        bee.emit("evt_gachaStart")
        self:hideUI()
        if self._params and self._params.confirmCb then
            self._params.confirmCb()
        end
    end
    self:saveCheckToggle()
end

function P:saveCheckToggle()
	if self.ToggleCheck:GetComponent("Toggle").isOn then
		GachaModel:setShowDrawNotice()
	end
end

return P