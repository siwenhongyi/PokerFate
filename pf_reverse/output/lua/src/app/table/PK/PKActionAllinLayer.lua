local P = class("PKActionAllLayer", require("app.table.PK.PKActionLayer"))

local PRE_ACTION = {
	CHECK_FOLD = 1,
	CALL_CURRENT = 2,
	CALL_ANY = 3,
    ALLIN = 3,
}

function P:setParams(params)
    P.super.setParams(self, params)
    self.data = params.data
end

function P:onAwake()
    self.ImageBg = self:find("ImageBg")
	self.BgAction = self:find("BgAction", self.ImageBg)
	self.BgActionPre = self:find("BgActionPre", self.ImageBg)

    self.FoldButton = self:find("FoldButton", self.BgAction)
    self.AllinButton = self:find("AllinButton", self.BgAction)

	self.ButtonPreFold = self:find("ButtonPreFold", self.BgActionPre)
	self.ButtonPreAllin = self:find("ButtonPreAllin", self.BgActionPre)
	self.PreActions = {
		[PRE_ACTION.CHECK_FOLD] = self.ButtonPreFold,
		[PRE_ACTION.ALLIN] = self.ButtonPreAllin,
	}


    bee.addClick(self.FoldButton, function()
        Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.FOLD})
    end)
    bee.addClick(self.AllinButton, function()
        Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.ALLIN})
    end)

    bee.addClick(self.ButtonPreFold, function()
		-- self:setPreActionCheck(PRE_ACTION.CHECK_FOLD)
		if self._preAction == PRE_ACTION.CHECK_FOLD then
			Net:sendReq("pb.PreActionREQ", {type = 0, chips = 0})
		else
			Net:sendReq("pb.PreActionREQ", {type = PRE_ACTION.CHECK_FOLD, chips = 0})
		end
    end)
    bee.addClick(self.ButtonPreAllin, function()
		if self._preAction == PRE_ACTION.ALLIN then
			Net:sendReq("pb.PreActionREQ", {type = 0, chips = 0})
		else
			Net:sendReq("pb.PreActionREQ", {type = PRE_ACTION.ALLIN, chips = 0})
		end
    end)
end

function P:refreshUI()
	if self.data:isMeOnSeat() and self.data:isMePlaying() and not self.data:isMeSittingOut() then
		if self.data:getActionIndex() == self.data:getMyPosition() then
			self:refreshContent()
		elseif self.data:getActionIndex() > 0 then
			self:refreshAutoBnts(true)
		else
			self:hide(true, true)
		end
	else
		self:hide(true, true)
	end
end

function P:refreshContent(fast)
	self:show(fast)
	self:showAutoBnts(false)
	self:showActionBnts(true)
end

