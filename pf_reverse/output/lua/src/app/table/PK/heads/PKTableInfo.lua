local P = class("PKTableInfo", Object)

-- 玩家显示在牌桌上的信息
function P:ctor()
    self._index = 1
    self.seatid = 1
end

function P:setIndex(i)
    self._index = i
    self.seatid = i
end

function P:setSeatId(i)
    self.seatid = i
end

function P:onAwake()
    self.ImageButton = self:find("ImageButton")
    self.BgInfo = self:find("BgInfo")
    self.ImageTag = self:find("ImageTag", self.BgInfo)
    self.ImageCheck = self:find("ImageCheck", self.BgInfo)
    self.ImageBet = self:find("ImageBet", self.BgInfo)
    self.ImageIcon = self:find("ImageIcon", self.ImageBet)
    self.TextPot = self:find("TextPot", self.ImageBet)
    self.TextTag = self:find("TextTag", self.ImageTag)

    self:setButtonVisible(false)
    self.ImageBet:SetActive(false)
    self:showTag()
end

function P:refreshUI()
    self.data, self.tableLayer = GameModel.data, GameModel.layer

    local info = self.data:getPlayer(self.seatid)
    self:setButtonVisible(false)
    if self.data:isPlaying() then
        self:showPot(info and info.bet_chip)
    else
        self:showPot(false)
    end
    self:refreshTag()
end

function P:refreshTag()
    local info = self.data:getPlayer(self.seatid)
    if info and info.on_seat and self.data:isPlaying() then
        local action_type = info.action_type
        if action_type == POKER_ACTION.WAIT and info.last_action_type ~= POKER_ACTION.NONE then
            action_type = info.last_action_type
        elseif (action_type == POKER_ACTION.SITED or action_type == POKER_ACTION.NONE) and info.bet_chip > 0 then
            action_type = POKER_ACTION.FOLD
        end
        self:showTag(action_type)
    elseif info and info.is_fold and self.data:isPlaying() then
        self:showTag(POKER_ACTION.FOLD)
    elseif info and self.data:isPlaying() and (info.action_type == POKER_ACTION.SITED or info.action_type == POKER_ACTION.NONE) and info.bet_chip > 0 then
        self:showTag(POKER_ACTION.FOLD)
    else
        self:showTag()
    end
end

function P:setButtonVisible(isShow)
    if self.data then
        self.ImageButton:SetActive(self.data:getDealerIndex() == self.seatid)
    else
        self.ImageButton:SetActive(isShow)
    end
end

function P:getButtonIcon()
    return self.ImageButton
end

function P:getPotPosition()
    return self.ImageBet.transform.position
end

function P:copyImageBet(isHide)
    if isHide then
        self.ImageBet:SetActive(false)
        self:showTag()
    end
    return CU.GameObject.Instantiate(self.ImageBet, self.transform, false)
end

function P:hidePot()
    if not self.data:isInAnte() then
        bee.tween(self.BgInfo)
        : to(0.2, {scale = bee.v3(1, 0, 1)})
        : link()
    end
end

function P:showPot(pot)
    if pot and pot > 0 then
        bee.setTextOrigin(self.TextPot, self.data:getBetChipsStr(pot))
        self.ImageBet:SetActive(true)
        self.BgInfo.transform.localScale = bee.v3one

        self:refreshTag()
    else
        self:showTag()
    end
end

function P:showTag(tag)
    if tag and POKER_ACTION_TAGS[tag] then
        if tag == POKER_ACTION.CALL or tag == POKER_ACTION.RAISE or tag == POKER_ACTION.BET then
            local info = self.data:getPlayer(self.seatid)
            if info and info.chips == 0 then
                tag = POKER_ACTION.ALLIN
            end
        end
        bee.setText(self.TextTag, _T(POKER_ACTION_TAGS[tag].name))
        bee.setIcon(self.ImageTag, POKER_ACTION_TAGS[tag].bg)
        self.ImageTag:SetActive(true)
        self.TextTag:SetActive(true)
        self.BgInfo.transform.localScale = bee.v3one
        if tag == POKER_ACTION.CHECK or tag == POKER_ACTION.SYS_CHECK then
            local info = self.data:getPlayer(self.seatid)
            if not info or info.bet_chip == 0 then
                self.ImageCheck:SetActive(true)
                self.ImageBet:SetActive(false)
            end
        elseif tag == POKER_ACTION.FOLD or tag == POKER_ACTION.SYS_FOLD or tag == POKER_ACTION.LEAVE_FOLD then
            local info = self.data:getPlayer(self.seatid)
            if not info or info.bet_chip == 0 then
                self.ImageCheck:SetActive(true)
                self.ImageBet:SetActive(false)
            end
        end
    else
        self.ImageTag:SetActive(false)
        self.TextTag:SetActive(false)
        self.ImageCheck:SetActive(false)
        self.ImageBet:SetActive(false)
    end
end

function P:collectBetToPot(collectDt)
	local info = self.data:getPlayer(self.seatid)
	if info.bet_chip == 0 then
		return
	end
	local function doCollect()
		if bee.isNull(self.node) or not GameModel.layer then
			return
		end

		local num = 5
		if info.bet_chip > self.data:getBigBlind() * 200 then
			num = 20
		elseif info.bet_chip >= self.data:getBigBlind() * 40 then
			num = 10
		end
		self:hidePot()
		local from = self.ImageBet.transform.position
		local to = self.tableLayer.ImagePot.transform.position

		self:flyChipsToPot(from, to, num, function()
		end)
	end
	doCollect()
end

function P:flyChipsToPot(from, to, num, cb)
	for i = 1, num do
		local eft = GameModel.layer:playUIEffect(self.data:getChipEft(), GameModel.layer.transform, nil, 3)
		eft.transform.position = from
		local pos = eft.transform.localPosition
		local ranPos = CU.Random.insideUnitCircle * 65
		bee.tween(eft)
		: to(0.066, {position = bee.v3(ranPos.x + pos.x, ranPos.y + pos.y)})
		: onComplete(function()
			bee.tween(eft, true)
			: to (0.533, {position = to})
			: ease(DT.Ease.InBack)
			: onComplete(function()
				GameModel.layer:putEffectItem(eft)
				if i == 1 then
					cb()
				end
			end)
			: link()
		end)
		: link()
	end
end

