local P = class("ActivityModel", BaseModel)

function P:ctor(logic)
    self.saveData = {}

    self._followedMediaList = {}
    self._linkEmailRwRemain = 0

	self.questionData = {}

    P.super.ctor(self)
end

-- 初始化活动数据
function P:initActInfo()
	self:requestFollowMedia()
	self:getBindRw()
	self:getSurveyData()
end

-- 获取活动页签展示列表
function P:getActShowList()
	local showList = {}
	for k, v in pairs(tpl_event_tab) do
		if v.type == ActivityType.Normal and v.event_id == ActivityId.SocialMedia then
			-- 关注社媒
			if self:isShowSocialMedia() then
				table.insert(showList, v)
			end
		elseif v.type == ActivityType.Normal and v.event_id == ActivityId.LinkEmail then
			-- 绑定邮箱
			if self:isShowLinkEmail() then
				table.insert(showList, v)
			end
		elseif v.type == ActivityType.TimeLimit and v.event_id == ActivityId.ActivitySignIn then
			-- 活动签到
			if ActivityNewmanCheckinModel:isActivityOpen() then
				table.insert(showList, v)
			end
		elseif v.type == ActivityType.TimeLimit and v.event_id == ActivityId.RetentionSurvey then
		-- 	--问卷调查
		-- 	if self.questionData.id ~= nil and self.questionData.status == 0 then
		-- 		table.insert(showList, v)
		-- end
		else
			table.insert(showList, v)
		end
	end

	table.sort(showList, function(a, b) return a.index < b.index end)
	return showList
end
function P:addRetentionSurvey(showList)
	for k, v in pairs(tpl_event_tab) do
		if v.type == ActivityType.TimeLimit and v.event_id == ActivityId.RetentionSurvey then
			--问卷调查
			if self.questionData.id ~= nil and self.questionData.status == 0 then
				table.insert(showList, v)
			end
		end
	end
	table.sort(showList, function(a, b) return a.index < b.index end)
	return showList
end

-- ============================== 关注社媒 ==============================
function P:requestFollowMedia()
    Net:post("game/getFollowMedia", nil, function(data)
        if data.code ~= 0 then
            return
        end

        self._followedMediaList = data.list or {}
    end)
end

function P:followMedia(media_id, cb)
    Net:post("game/followMedia", {lang = LanguageManager:getLanguage(), media_id = media_id}, function(data)
        if data.code ~= 0 then
            return
        end

        table.insert(self._followedMediaList, media_id)
        if data.item_list then
	        bee.showUiTask("BackpackClaimResult", {items = data.item_list}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
	        bee.runTask(POP_TAG.Reward)
	    end

        if cb then
        	cb()
        end
    end)
end

function P:getCurFollowCfg()
	local curLan = LanguageManager:getLanguage()
	for k,v in pairs(tpl_followmedia_config) do
		if v.lang == curLan then
			return v
		end
	end
end

function P:getIsFollowed(id)
	for k,v in pairs(self._followedMediaList) do
		if v == id then
			return true
		end
	end
	return false
end

function P:isShowSocialMedia()
	local cfg = self:getCurFollowCfg()
	if not cfg then
		return false
	end

	for k,v in pairs(cfg.media_platform) do
		if not self:getIsFollowed(v) then
			return true
		end
	end
	return false
end

function P:getSocialMediaCfg(media_id)
	local curLan = LanguageManager:getLanguage()
	for _, v in pairs(tpl_medialink_config) do
		if curLan == v.lang and media_id == v.media_id then
			return v
		end
	end
end

-- ============================== 绑定邮箱 ==============================
function P:evt_refreshBindEmail()
	self:getBindRw()
end

function P:getBindRw()
    Net:post("game/getBindRw", nil, function(data)
        if data.code ~= 0 then
            return
        end

        self._linkEmailRwRemain = data.remain
        bee.emit("evt_refreshEmailBindRw")
    end)
end

function P:receiveEmailBindReward()
    Net:post("game/recBindRw", nil, function(data)
        if data.code ~= 0 then
            return
        end

        self._linkEmailRwRemain = data.remain

        if data.item_list then
	        bee.showUiTask("BackpackClaimResult", {items = data.item_list}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
	        bee.runTask(POP_TAG.Reward)
	    end

        self:getBindRw()
    end)
end

function P:isCanReceiveLinkRw()
	return self._linkEmailRwRemain and self._linkEmailRwRemain > 0
end

function P:isShowLinkEmail()
	local email = PlayerModel:getBindEmail()
	if (email and email ~= "") and self._linkEmailRwRemain == 0 then
		return false
	end
	return true
end

-- ============================== 问卷调查 ==============================

--获取答题数据
function P:getSurveyData(cb)
	Net:post("activity/survey", {avenue_id = G_CHNL_ID}, function (data)
		if data.code ~= 0 then
            return
        end
		
		self.questionData.id = data.id
		self.questionData.status = data.status
		self.questionData.list = data.questions
		self.questionData.rewards = data.rewards

		if cb then
			cb()
		end

		self:refreshQuestionReddot()
	end)
end

--提交答案
function P:submitSurveyAnswer(id, answer, order)
	local args = {}
	args.id = id
	args.answers = {}
	for _,v in pairs(order) do
		local data = {}
		for _,av in pairs(answer) do
			if av.qid == v then
				data.question_id = av.qid
				if av.sltIndex then
					data.option_id = {av.sltIndex}
				end
				if av.sltIndexs then
					data.option_id = av.sltIndexs
				end
				if av.str then
					data.content = av.str
				end
				table.insert(args.answers, data)
				break
			end
		end
	end
	
	Net:post("activity/survey/answer", args, function (data)
		if data.code ~= 0 then
			return
		end
		UiManager:showUI("BackpackClaimResult", {items = data.rewards})
		self.questionData.status = 2
		bee.emit("evt_getQuestionRewardCallback")
		self:refreshQuestionReddot()
	end)
end

--领取奖励
function P:getQuestionRewards(id)
	-- Net:post("activity/survey/claimReward", {id = id}, function (data)
	-- 	if data.code ~= 0 then
	-- 		return
	-- 	end
	-- 	UiManager:showUI("BackpackClaimResult", {items = data.rewards})
	-- 	self.questionData.status = 2
	-- 	bee.emit("evt_getQuestionRewardCallback")
	-- end)
end

function P:getQuestionData()
	return self.questionData
end

function P:refreshQuestionReddot()
	RedManager:removeTag(RedTag.ActivityRetentionSurvey)
	if self.questionData.id == nil then
		return
	end
		
	local reddot = self.questionData.status < 2
	if reddot then
		RedManager:addTag(RedTag.ActivityRetentionSurvey)
	end
end

return P