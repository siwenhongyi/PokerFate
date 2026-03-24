local P = {}
GameABTestManager = P

function P:init(testType)
	self._configs = {
	}

	self._bConfigs = {}
	self._aConfigs = {}
	for _, v in ipairs(self._configs) do
		self._aConfigs[v] = _G[v]
		self._aConfigs[v .. "_list"] = _G[v .. "_list"]
		self._bConfigs[v] = _G[v .. "_b"]
		self._bConfigs[v .. "_list"] = _G[v .. "_b_list"]
	end

	self:refreshConfigs()
end

function P:refreshConfigs()
	if SdkHelper:isTestB() then
		for k, v in pairs(self._bConfigs) do
			_G[k] = v
		end
	else
		for k, v in pairs(self._aConfigs) do
			_G[k] = v
		end
	end
end

